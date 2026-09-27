"""
services/document_service.py
=============================
Couche métier de la gestion documentaire (upload, indexation, suppression,
listing) utilisée par le router admin.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from config import get_settings
from ingestion.document_loader import SUPPORTED_EXTENSIONS
from ingestion.embedder import BeHaveVectorStore
from ingestion.manifest import ManifestEntry, load_manifest, upsert_entry
from ingestion.pipeline import build_chunks

logger = logging.getLogger(__name__)

UPLOAD_DIR        = get_settings().uploaded_docs_dir
ORIGINAL_DOCS_DIR = get_settings().documents_dir

# Instance partagée avec le pipeline RAG (injectée au démarrage) : le modèle
# d'embedding n'est chargé qu'une fois.
_vector_store: BeHaveVectorStore | None = None


def set_vector_store(store: BeHaveVectorStore) -> None:
    """Injecte l'instance BeHaveVectorStore déjà créée par le pipeline RAG."""
    global _vector_store
    _vector_store = store


def get_vector_store() -> BeHaveVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = BeHaveVectorStore()
    return _vector_store


def validate_file(filename: str, file_size: int) -> str | None:
    """Retourne un message d'erreur si l'extension ou la taille est invalide, sinon None."""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        return (
            f"Format '{suffix}' non supporté. "
            f"Formats acceptés : {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    max_mb = get_settings().max_upload_size_mb
    if file_size > max_mb * 1024 * 1024:
        return f"Fichier trop volumineux. Taille maximale : {max_mb} Mo"

    return None


def save_file_to_disk(filename: str, content: bytes) -> Path:
    """Enregistre le fichier dans UPLOAD_DIR et retourne son chemin."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / filename
    file_path.write_bytes(content)
    logger.info("Fichier sauvegardé : %s (%d octets)", file_path, len(content))
    return file_path


def delete_file_from_disk(filename: str) -> bool:
    """Supprime un fichier de UPLOAD_DIR. Retourne False s'il est introuvable."""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        logger.warning("Fichier introuvable pour suppression : %s", file_path)
        return False

    file_path.unlink()
    logger.info("Fichier supprimé du disque : %s", file_path)
    return True


def register_document_metadata(filename: str, module: str | None, title: str | None) -> None:
    """
    Déclare module/titre d'un document dans le manifeste.
    Sans module ni titre fournis, l'éventuelle entrée existante est conservée.
    """
    if module or title:
        upsert_entry(
            get_settings().manifest_path,
            filename,
            ManifestEntry(module=module, title=title),
        )


def index_document(file_path: Path) -> int:
    """
    Indexe un fichier (même pipeline que run_indexation.py) et retourne le
    nombre de chunks indexés.

    Les chunks d'une version précédente du même fichier sont supprimés d'abord :
    un simple upsert laisserait des chunks en surnombre si la nouvelle version
    en produit moins.
    """
    chunks = build_chunks(
        file_path,
        load_manifest(get_settings().manifest_path),
        extra_metadata={
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "origin":      "admin_upload",
        },
    )
    if not chunks:
        raise ValueError(f"Le document '{file_path.name}' est vide ou illisible.")

    store = get_vector_store()
    replaced = store.delete_by_source(file_path.name)
    if replaced:
        logger.info("Version précédente remplacée : %d chunks supprimés", replaced)
    store.add_documents(chunks)

    logger.info("Indexation terminée : %s — %d chunks", file_path.name, len(chunks))
    return len(chunks)


def delete_document_from_index(filename: str) -> int:
    """Supprime tous les chunks d'un document et retourne leur nombre."""
    return get_vector_store().delete_by_source(filename)


def list_indexed_documents() -> list[dict]:
    """Documents distincts présents dans l'index, avec nombre de chunks et taille sur disque."""
    docs: dict[str, dict] = {}

    for meta in get_vector_store().get_all_metadatas():
        source = meta.get("source", "inconnu")
        if source not in docs:
            docs[source] = {
                "filename":     source,
                "chunks_count": 0,
                "uploaded_at":  meta.get("uploaded_at", "N/A"),
                "file_size_kb": _get_file_size_kb(source),
            }
        docs[source]["chunks_count"] += 1

    return list(docs.values())


def _get_file_size_kb(filename: str) -> float:
    """Taille en Ko, cherchée dans UPLOAD_DIR puis ORIGINAL_DOCS_DIR (0.0 si introuvable)."""
    for directory in (UPLOAD_DIR, ORIGINAL_DOCS_DIR):
        file_path = directory / filename
        if file_path.exists():
            return round(file_path.stat().st_size / 1024, 2)
    return 0.0
