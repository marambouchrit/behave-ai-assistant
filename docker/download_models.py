"""Télécharge dans l'image les modèles configurés (EMBEDDING_MODEL, RERANKER_MODEL)."""

from sentence_transformers import CrossEncoder, SentenceTransformer

from config import get_settings

settings = get_settings()
SentenceTransformer(settings.embedding_model)
CrossEncoder(settings.reranker_model)
print(f"Modèles prêts : {settings.embedding_model}, {settings.reranker_model}")
