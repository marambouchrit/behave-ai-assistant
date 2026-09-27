"""
retriever.py
============
Recherche des chunks pertinents dans la documentation BeHave pour une question.

Deux étages (reranking activé, défaut) :
    1. recherche vectorielle ChromaDB   → RAG_CANDIDATES_K candidats (~20)
    2. reranking par cross-encoder      → tri par pertinence, filtrage par
                                          RAG_MIN_RERANK_SCORE, RAG_K premiers

Un étage (reranking désactivé) :
    recherche vectorielle → filtrage par RAG_MIN_COSINE_SIMILARITY → RAG_K premiers

Le filtrage par pertinence est fait ici et uniquement ici, avec un seul seuil
actif selon le mode. Chaque chunk retourné porte metadata["relevance_score"] :
le score qui a servi à le classer et à le filtrer.
"""

import logging

from config import get_settings
from ingestion.document_loader import Document
from ingestion.embedder import BeHaveVectorStore
from rag.reranker import Reranker

logger = logging.getLogger(__name__)


class BeHaveRetriever:
    """
    Encapsule BeHaveVectorStore (+ Reranker) avec filtrage par score.
    retrieve() retourne toujours une list triée par pertinence décroissante.
    """

    def __init__(
        self,
        store: BeHaveVectorStore | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        settings = get_settings()

        if store is None:
            logger.info("Chargement base vectorielle : %s", settings.chroma_db_dir)
            store = BeHaveVectorStore()
        store.ensure_compatible()
        self.store = store

        if reranker is None and settings.reranker_enabled:
            reranker = Reranker(settings.reranker_model, settings.reranker_max_length)
        self.reranker = reranker

        self.candidates_k = settings.rag_candidates_k
        self.min_score = (
            settings.rag_min_rerank_score if self.reranker
            else settings.rag_min_cosine_similarity
        )

        logger.info(
            "Retriever prêt — %d documents indexés | reranker=%s | min_score=%.2f",
            self.store.get_collection_info()["document_count"],
            self.reranker.model_name if self.reranker else "désactivé",
            self.min_score,
        )

    def retrieve(self, query: str, k: int) -> list[Document]:
        """
        Retourne au plus k chunks pertinents, triés par pertinence décroissante
        (liste vide si aucun ne passe le seuil).
        """
        if not query or not query.strip():
            logger.warning("retrieve() : question vide ignorée.")
            return []

        if self.reranker:
            candidates = self.store.search(query, k=max(k, self.candidates_k))
            ranked = [
                _with_relevance(c, c.metadata["rerank_score"])
                for c in self.reranker.rerank(query, candidates)
            ]
        else:
            ranked = [
                _with_relevance(c, c.metadata["similarity_score"])
                for c in self.store.search(query, k=k)
            ]

        results = [c for c in ranked if c.metadata["relevance_score"] >= self.min_score][:k]

        if not results:
            logger.info("Aucun chunk pertinent pour : %r", query)
        else:
            self._log_results(results)
        return results

    def _log_results(self, results: list[Document]) -> None:
        for i, doc in enumerate(results):
            logger.debug(
                "  [%d] relevance=%.4f (cos=%.4f) | %s",
                i + 1,
                doc.metadata["relevance_score"],
                doc.metadata.get("similarity_score", float("nan")),
                doc.metadata.get("module", "?"),
            )


def _with_relevance(chunk: Document, score: float) -> Document:
    chunk.metadata["relevance_score"] = score
    return chunk


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    retriever = BeHaveRetriever()

    questions = [
        "Comment créer un client dans BeHave Master Data ?",
        "Quels modèles IA utilise BeHave Predictive ?",
        "Comment fonctionne la gouvernance des accès SAP ?",
    ]

    for question in questions:
        logger.info("Question : %s", question)
        for i, chunk in enumerate(retriever.retrieve(question, k=3)):
            logger.info(
                "  [%d] relevance=%.4f | %s",
                i + 1, chunk.metadata["relevance_score"], chunk.metadata.get("module", "?"),
            )
            logger.info("       %s...", chunk.page_content[:120])
