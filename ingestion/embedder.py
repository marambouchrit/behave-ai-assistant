"""
embedder.py
===========
Génération des embeddings et stockage vectoriel dans ChromaDB
(collection permanente de la documentation BeHave).

Score de pertinence : chaque Document retourné par search() porte
metadata["similarity_score"] = similarité cosinus brute (1 - distance cosinus),
dans [-1, 1] — plus élevé = plus pertinent.

Texte embeddé vs texte stocké : le vecteur d'un chunk est calculé sur
"<préfixe passage><titre — section>\n<texte>", ce qui situe le chunk dans son
document ; ChromaDB stocke le texte seul, transmis tel quel au LLM.

Compatibilité de l'index : le nom du modèle d'embedding est enregistré dans la
metadata de la collection. Un index construit avec un autre modèle (vecteurs
incompatibles) est détecté au chargement et doit être reconstruit avec
`python -m ingestion.run_indexation --reset`.
"""

import logging
from pathlib import Path

from config import get_settings
from ingestion.document_loader import Document

logger = logging.getLogger(__name__)

COLLECTION_NAME = "behave_docs"

_EMBEDDING_MODEL_KEY = "embedding_model"


class IncompatibleIndexError(RuntimeError):
    """L'index ChromaDB a été construit avec un autre modèle d'embedding."""


class BeHaveVectorStore:
    """Encapsule ChromaDB + SentenceTransformer pour le pipeline RAG BeHave."""

    def __init__(
        self,
        persist_directory: str | Path | None = None,
        collection_name: str = COLLECTION_NAME,
        embedding_model: str | None = None,
    ) -> None:
        settings = get_settings()
        self.persist_directory    = str(persist_directory or settings.chroma_db_dir)
        self.collection_name      = collection_name
        self.embedding_model_name = embedding_model or settings.embedding_model
        self._query_prefix        = settings.embedding_query_prefix
        self._passage_prefix      = settings.embedding_passage_prefix
        self._client            = None
        self._collection        = None
        self._embedding_model   = None
        self._doc_count: int    = 0
        self._modules_cache: list[str] | None = None

        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
        self._init_chromadb()
        self._init_embedding_model()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _collection_metadata(self) -> dict:
        return {"hnsw:space": "cosine", _EMBEDDING_MODEL_KEY: self.embedding_model_name}

    def _init_chromadb(self) -> None:
        """Initialise le client ChromaDB persistant et la collection permanente."""
        import chromadb
        from chromadb.errors import NotFoundError

        self._client = chromadb.PersistentClient(path=self.persist_directory)

        # get puis create (et non get_or_create) : la metadata d'une collection
        # existante — dont le modèle ayant servi à l'indexer — ne doit jamais
        # être réécrite.
        try:
            self._collection = self._client.get_collection(name=self.collection_name)
        except NotFoundError:
            self._collection = self._client.create_collection(
                name=self.collection_name,
                metadata=self._collection_metadata(),
            )

        self._doc_count = self._collection.count()
        logger.info(
            "ChromaDB prêt — collection '%s' (%d documents)",
            self.collection_name, self._doc_count,
        )

    def _init_embedding_model(self) -> None:
        """Charge le modèle SentenceTransformer."""
        from sentence_transformers import SentenceTransformer

        logger.info("Chargement du modèle : %s ...", self.embedding_model_name)
        self._embedding_model = SentenceTransformer(self.embedding_model_name)
        dim = self._embedding_model.get_embedding_dimension()
        logger.info(
            "Modèle chargé — %d dimensions, %d tokens max",
            dim, self._embedding_model.max_seq_length,
        )

    @property
    def indexed_with(self) -> str | None:
        """Modèle d'embedding avec lequel l'index existant a été construit."""
        return (self._collection.metadata or {}).get(_EMBEDDING_MODEL_KEY)

    @property
    def is_compatible(self) -> bool:
        """True si l'index est vide ou construit avec le modèle courant."""
        return self._doc_count == 0 or self.indexed_with == self.embedding_model_name

    def ensure_compatible(self) -> None:
        """
        Raises:
            IncompatibleIndexError : index construit avec un autre modèle.
        """
        if not self.is_compatible:
            raise IncompatibleIndexError(
                f"Index ChromaDB construit avec '{self.indexed_with}', modèle "
                f"configuré : '{self.embedding_model_name}'. Reconstruisez l'index : "
                f"python -m ingestion.run_indexation --reset"
            )

    # ── Embeddings ────────────────────────────────────────────────────────────

    def _embed_texts(
        self,
        texts: list[str],
        show_progress: bool = False,
    ) -> list[list[float]]:
        """Encode une liste de textes en vecteurs normalisés."""
        embeddings = self._embedding_model.encode(
            texts,
            show_progress_bar=show_progress,
            batch_size=32,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def _passage_text(self, doc: Document) -> str:
        """Texte embeddé d'un chunk : préfixe + contexte (titre, section) + texte."""
        return f"{self._passage_prefix}{doc.with_context()}"

    def _warn_if_truncated(self, ids: list[str], texts: list[str]) -> None:
        """Signale les textes plus longs que la fenêtre du modèle (fin ignorée)."""
        tokenizer = self._embedding_model.tokenizer
        max_len   = self._embedding_model.max_seq_length
        too_long  = [
            (chunk_id, n_tokens)
            for chunk_id, text in zip(ids, texts)
            if (n_tokens := len(tokenizer(text)["input_ids"])) > max_len
        ]
        for chunk_id, n_tokens in too_long:
            logger.warning(
                "Chunk tronqué à l'embedding : %s (%d tokens > %d) — "
                "réduire CHUNK_SIZE_CHARS.",
                chunk_id, n_tokens, max_len,
            )

    # ── Écriture ──────────────────────────────────────────────────────────────

    def add_documents(
        self,
        documents: list[Document],
        batch_size: int = 100,
    ) -> int:
        """
        Encode et indexe une liste de Documents dans la collection permanente
        (upsert — idempotent).

        Returns:
            Nombre total de chunks indexés lors de cet appel.

        Raises:
            IncompatibleIndexError : index construit avec un autre modèle.
        """
        if not documents:
            logger.warning("add_documents appelé avec une liste vide.")
            return 0

        self.ensure_compatible()

        total_batches = (len(documents) + batch_size - 1) // batch_size
        total_added   = 0

        logger.info(
            "Indexation de %d chunks en %d batch(es)...",
            len(documents), total_batches,
        )

        for batch_num in range(total_batches):
            start = batch_num * batch_size
            end   = min(start + batch_size, len(documents))
            batch = documents[start:end]

            logger.info(
                "  Batch %d/%d (chunks %d–%d)...",
                batch_num + 1, total_batches, start, end - 1,
            )

            ids = [
                doc.metadata.get("chunk_id", f"chunk_{start + i:06d}")
                for i, doc in enumerate(batch)
            ]
            passages = [self._passage_text(doc) for doc in batch]
            self._warn_if_truncated(ids, passages)

            self._collection.upsert(
                ids=ids,
                documents=[doc.page_content for doc in batch],
                embeddings=self._embed_texts(passages, show_progress=True),
                metadatas=[_clean_metadata(doc.metadata) for doc in batch],
            )

            total_added += len(batch)
            logger.info("    %d/%d chunks indexés", total_added, len(documents))

        self._doc_count     = self._collection.count()
        self._modules_cache = None
        logger.info(
            "Indexation terminée — %d ajoutés, %d total dans la collection.",
            total_added, self._doc_count,
        )
        return total_added

    def clear_collection(self, confirm: bool = False) -> None:
        """
        Vide la collection permanente ChromaDB et la recrée pour le modèle
        d'embedding courant.

        Raises:
            RuntimeError : si confirm=False (protection contre suppression accidentelle).
        """
        if not confirm:
            raise RuntimeError(
                "clear_collection() nécessite confirm=True. "
                "Appelez clear_collection(confirm=True) explicitement."
            )

        self._client.delete_collection(self.collection_name)
        self._collection = self._client.create_collection(
            name=self.collection_name,
            metadata=self._collection_metadata(),
        )
        self._doc_count     = 0
        self._modules_cache = None
        logger.info("Collection '%s' vidée.", self.collection_name)

    def delete_by_source(self, source: str) -> int:
        """
        Supprime tous les chunks d'un document via son champ 'source'.

        Returns:
            int : nombre de chunks supprimés
        """
        results   = self._collection.get(where={"source": source})
        chunk_ids = results.get("ids", [])

        if not chunk_ids:
            return 0

        self._collection.delete(ids=chunk_ids)
        self._doc_count     = self._collection.count()
        self._modules_cache = None
        logger.info(
            "delete_by_source : %d chunks supprimés pour '%s'",
            len(chunk_ids), source,
        )
        return len(chunk_ids)

    # ── Lecture ───────────────────────────────────────────────────────────────

    def search(self, query: str, k: int = 3) -> list[Document]:
        """
        Recherche les k chunks les plus similaires à la requête dans la
        collection permanente (documentation BeHave).
        Retourne [] si la collection est vide.

        Raises:
            IncompatibleIndexError : index construit avec un autre modèle.
        """
        if self._doc_count == 0:
            logger.warning("search() appelé sur une collection vide.")
            return []

        self.ensure_compatible()

        effective_k     = min(k, self._doc_count)
        query_embedding = self._embed_texts(
            [f"{self._query_prefix}{query}"], show_progress=False,
        )[0]

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=effective_k,
            include=["documents", "metadatas", "distances"],
        )

        return _build_documents_from_query(results)

    def get_collection_info(self) -> dict:
        """Résumé de la collection — utilise le cache _doc_count."""
        return {
            "collection_name":   self.collection_name,
            "document_count":    self._doc_count,
            "persist_directory": self.persist_directory,
            "embedding_model":   self.embedding_model_name,
        }

    def get_all_metadatas(self) -> list[dict]:
        """
        Retourne toutes les métadonnées de la collection sans les vecteurs.

        Returns:
            list[dict] : métadonnées de chaque chunk indexé
        """
        results = self._collection.get(include=["metadatas"])
        return results.get("metadatas", [])

    def list_modules(self) -> list[str]:
        """
        Modules BeHave réellement présents dans l'index (triés, sans doublon).
        Mis en cache, invalidé à chaque écriture dans la collection.
        """
        if self._modules_cache is None:
            self._modules_cache = sorted({
                meta["module"]
                for meta in self.get_all_metadatas()
                if meta.get("module")
            })
        return list(self._modules_cache)


def _build_documents_from_query(results: dict) -> list[Document]:
    """Reconstruit une liste de Document à partir d'un résultat ChromaDB .query()."""
    if not results["documents"] or not results["documents"][0]:
        return []

    retrieved: list[Document] = []
    for text, metadata, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # Collection créée avec hnsw:space="cosine" : distance = 1 - cos.
        similarity = round(1.0 - distance, 4)
        retrieved.append(Document(
            page_content=text,
            metadata={**metadata, "similarity_score": similarity},
        ))
    return retrieved


def _clean_metadata(metadata: dict) -> dict:
    """
    ChromaDB n'accepte que str, int, float, bool.
    Les valeurs None sont omises (clé absente = information inconnue).
    """
    clean: dict = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            clean[key] = value
        else:
            clean[key] = str(value)
    return clean
