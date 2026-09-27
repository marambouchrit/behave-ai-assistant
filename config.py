"""
config.py
=========
Configuration centralisée du projet (backend, pipeline RAG, ingestion).

Toutes les valeurs sont lues une seule fois depuis les variables d'environnement
et le fichier .env à la racine du projet, puis validées et typées par
pydantic-settings. Aucun autre module ne lit os.environ ni n'appelle load_dotenv.

Les secrets sont optionnels au niveau du modèle : chaque point d'entrée exige
uniquement ceux dont il a besoin via require_settings() (l'indexation n'a pas
besoin de la clé Groq, par exemple).

Usage :
    from config import get_settings
    settings = get_settings()
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT: Path = Path(__file__).resolve().parent
_DATA_DIR: Path    = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Auth, base de données, API ────────────────────────────────────────────
    jwt_secret_key:          str = ""
    jwt_expire_minutes:      int = Field(default=480, gt=0)
    # Anti brute-force sur /auth/login, par adresse IP (syntaxe de `limits`).
    login_rate_limit:        str = "5/minute"
    database_url:            str = ""
    # Origines autorisées à appeler l'API (frontend). Dans .env : liste JSON.
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    max_upload_size_mb:      int = Field(default=20, gt=0)

    # ── Groq (LLM) ────────────────────────────────────────────────────────────
    groq_api_key:          str   = ""
    groq_model_text:       str   = "openai/gpt-oss-20b"
    groq_max_tokens:       int   = Field(default=1024, gt=0)
    groq_temperature:      float = Field(default=0.2, ge=0.0, le=2.0)
    groq_timeout_seconds:  float = Field(default=30.0, gt=0)
    # Le SDK Groq réessaie lui-même (backoff exponentiel) sur 408/409/429/5xx
    # et les erreurs de connexion.
    groq_max_retries:      int   = Field(default=2, ge=0)
    # gpt-oss est un modèle à raisonnement : ses tokens de raisonnement sont
    # décomptés de groq_max_tokens. "low" limite le risque de réponse vide
    # (finish_reason=length) et la latence.
    groq_reasoning_effort: Literal["low", "medium", "high"] | None = "low"

    # ── RAG ───────────────────────────────────────────────────────────────────
    # Nombre de chunks transmis au LLM (après reranking s'il est activé).
    rag_k:                    int = Field(default=4, gt=0)
    # Candidats du premier étage (recherche vectorielle) soumis au reranker.
    rag_candidates_k:         int = Field(default=20, gt=0)
    rag_max_history_turns:    int = Field(default=10, ge=0)
    rag_history_token_budget: int = Field(default=6000, ge=0)
    # Seuil de pertinence du mode SANS reranker, en similarité cosinus brute.
    # Dépend du modèle d'embedding : à recalibrer à chaque changement de modèle
    # (calibration : evaluation/results.md).
    rag_min_cosine_similarity: float = Field(default=0.81, ge=-1.0, le=1.0)

    # ── Reranking (second étage) ──────────────────────────────────────────────
    # Activé : le seuil de pertinence est rag_min_rerank_score (score du
    # cross-encoder) et rag_min_cosine_similarity n'est plus appliqué.
    # Modèle et seuil calibrés par `python -m evaluation.run_eval`.
    reranker_enabled:     bool  = True
    reranker_model:       str   = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    reranker_max_length:  int   = Field(default=512, gt=0)
    rag_min_rerank_score: float = Field(default=0.75, ge=0.0, le=1.0)

    # ── Base vectorielle & embeddings ─────────────────────────────────────────
    chroma_db_dir:   Path = _DATA_DIR / "chroma_db"
    # Multilingue (FR/EN, recherche cross-lingue), 512 tokens max par texte.
    embedding_model: str  = "intfloat/multilingual-e5-base"
    # Préfixes attendus par la famille E5 ; laisser vides pour un modèle qui
    # n'en utilise pas.
    embedding_query_prefix:   str = "query: "
    embedding_passage_prefix: str = "passage: "

    # ── Chunking ──────────────────────────────────────────────────────────────
    # ~1200 caractères ≈ 300-400 tokens : tient dans la fenêtre du modèle
    # d'embedding avec l'en-tête de contexte (titre, section). L'indexation
    # signale tout chunk qui la dépasserait.
    chunk_size_chars:    int = Field(default=1200, gt=0)
    chunk_overlap_chars: int = Field(default=150, ge=0)

    # ── Documents ─────────────────────────────────────────────────────────────
    documents_dir:     Path = _DATA_DIR / "documents"
    uploaded_docs_dir: Path = _DATA_DIR / "uploaded_docs"
    # Métadonnées déclarées par document (module, titre) — voir ingestion/manifest.py
    manifest_path:     Path = _DATA_DIR / "manifest.yaml"


@lru_cache
def get_settings() -> Settings:
    """Instance unique, construite au premier appel."""
    return Settings()


def require_settings(*names: str) -> None:
    """
    Vérifie que les paramètres indispensables à un point d'entrée sont renseignés.

    Raises:
        RuntimeError : liste toutes les variables manquantes d'un coup.
    """
    settings = get_settings()
    missing  = [name.upper() for name in names if not getattr(settings, name)]
    if missing:
        raise RuntimeError(
            f"Variable(s) manquante(s) dans .env : {', '.join(missing)}"
        )
