"""
pipeline.py
===========
Construction des chunks d'un fichier : chargement → metadata → découpage.

Point d'entrée unique partagé par l'indexation offline (run_indexation.py)
et l'upload admin (backend/services/document_service.py).
"""

from pathlib import Path

from ingestion.chunker import chunk_segments
from ingestion.document_loader import Document, load_document
from ingestion.manifest import ManifestEntry


def build_chunks(
    file_path: Path,
    manifest: dict[str, ManifestEntry],
    extra_metadata: dict | None = None,
) -> list[Document]:
    """
    Charge un fichier, lui applique les métadonnées déclarées dans le
    manifeste (module, titre), puis le découpe en chunks.

    Le titre du manifeste prime sur celui extrait du document (style "Title"
    d'un DOCX) ; sans l'un ni l'autre, aucun titre n'est stocké.
    """
    entry    = manifest.get(file_path.name, ManifestEntry())
    segments = load_document(file_path)

    for segment in segments:
        if entry.module:
            segment.metadata["module"] = entry.module
        if entry.title:
            segment.metadata["title"] = entry.title
        if extra_metadata:
            segment.metadata.update(extra_metadata)

    return chunk_segments(segments)
