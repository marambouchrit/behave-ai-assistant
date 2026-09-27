"""
reranker.py
===========
Second étage du retrieval : reclassement des candidats par un cross-encoder.

Le retrieval vectoriel (bi-encoder) compare deux vecteurs calculés
indépendamment : rapide, mais ses scores cosinus sont peu discriminants
(avec multilingual-e5, questions pertinentes et hors sujet se chevauchent).
Un cross-encoder lit la question ET le chunk ensemble et produit un score de
pertinence bien plus fiable, au prix d'une inférence par paire — d'où son
application aux seuls ~20 meilleurs candidats du premier étage.

Le score est écrit dans metadata["rerank_score"] ; il sert ensuite au filtrage
hors périmètre et au choix du chunk de référence (module, sources).

Échelle : une sigmoïde est appliquée explicitement, si bien que le score est
toujours dans [0, 1] quel que soit le modèle (sans elle, certains
cross-encoders renvoient des logits bruts non bornés, et le seuil
RAG_MIN_RERANK_SCORE changerait de sens d'un modèle à l'autre).
"""

import logging
import time

from ingestion.document_loader import Document

logger = logging.getLogger(__name__)

# Petits lots : chaque paire est complétée (padding) jusqu'à la plus longue du
# lot ; des lots de 8 limitent ce gaspillage sur CPU (mesuré ≈ -30 % de latence
# par rapport à 32 sur ce corpus, chunks de 50 à 300 tokens).
_BATCH_SIZE = 8


class Reranker:
    """Cross-encoder de reclassement (sentence-transformers)."""

    def __init__(self, model_name: str, max_length: int = 512) -> None:
        import torch
        from sentence_transformers import CrossEncoder

        logger.info("Chargement du reranker : %s ...", model_name)
        self.model_name = model_name
        self._model = CrossEncoder(
            model_name,
            max_length=max_length,
            activation_fn=torch.nn.Sigmoid(),
        )
        logger.info("Reranker prêt.")

    def score(self, query: str, chunks: list[Document]) -> list[float]:
        """Scores de pertinence (question, chunk) dans [0, 1], dans l'ordre des chunks."""
        if not chunks:
            return []
        pairs = [(query, chunk.with_context()) for chunk in chunks]
        scores = self._model.predict(pairs, batch_size=_BATCH_SIZE, show_progress_bar=False)
        return [float(s) for s in scores]

    def rerank(self, query: str, chunks: list[Document]) -> list[Document]:
        """
        Retourne les chunks triés par pertinence décroissante, chacun portant
        metadata["rerank_score"].
        """
        start  = time.perf_counter()
        scores = self.score(query, chunks)

        reranked = [
            Document(
                page_content=chunk.page_content,
                metadata={**chunk.metadata, "rerank_score": round(score, 4)},
            )
            for chunk, score in zip(chunks, scores)
        ]
        reranked.sort(key=lambda c: c.metadata["rerank_score"], reverse=True)

        logger.debug(
            "Reranking de %d candidats en %.0f ms",
            len(chunks), (time.perf_counter() - start) * 1000,
        )
        return reranked
