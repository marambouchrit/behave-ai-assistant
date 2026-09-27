"""
chunker.py
==========
Découpage des segments d'un document (pages PDF, sections DOCX) en chunks
pour l'indexation RAG.

Chaque chunk hérite de la metadata de son segment (source, page, section,
module, titre) et reçoit un identifiant stable : "<source>__<index>".
Aucun plafond de chunks par document : tout le contenu est indexé.

Sections courtes : des sous-sections consécutives qui tiennent ensemble dans
un chunk sont fusionnées (un titre suivi d'une phrase isolée donne un vecteur
pauvre). La section retenue est leur ancêtre commun dans la hiérarchie des
titres ; des sections sans ancêtre commun ne sont jamais fusionnées.
Les pages PDF ne sont jamais fusionnées (numéro de page exact).
"""

import re
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import get_settings
from ingestion.document_loader import SECTION_SEPARATOR, Document

logger = logging.getLogger(__name__)

# En dessous, un chunk n'a pas de contenu exploitable (titre de page isolé…).
_MIN_CHUNK_CHARS = 30

_RE_INVALID_ID_CHARS        = re.compile(r"[^\w\-.]")
_RE_CONSECUTIVE_UNDERSCORES = re.compile(r"_+")


def _sanitize_chunk_id(raw_id: str) -> str:
    """
    Nettoie un identifiant pour ChromaDB.
    ChromaDB n'accepte que [a-zA-Z0-9_-.].
    """
    sanitized = _RE_INVALID_ID_CHARS.sub("_", raw_id)
    sanitized = _RE_CONSECUTIVE_UNDERSCORES.sub("_", sanitized)
    return sanitized.strip("_")


def _common_section(a: str, b: str) -> str | None:
    """Plus long préfixe commun de deux chemins de titres, None si aucun."""
    common: list[str] = []
    for left, right in zip(a.split(SECTION_SEPARATOR), b.split(SECTION_SEPARATOR)):
        if left != right:
            break
        common.append(left)
    return SECTION_SEPARATOR.join(common) or None


def _merge_small_sections(segments: list[Document], max_chars: int) -> list[Document]:
    """Fusionne les sections consécutives courtes qui partagent un ancêtre commun."""
    merged: list[Document] = []
    for segment in segments:
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and previous.metadata.get("section")
            and segment.metadata.get("section")
            and len(previous.page_content) + len(segment.page_content) + 2 <= max_chars
        ):
            common = _common_section(previous.metadata["section"], segment.metadata["section"])
            if common:
                previous.page_content = f"{previous.page_content}\n\n{segment.page_content}"
                previous.metadata["section"] = common
                continue
        merged.append(Document(page_content=segment.page_content, metadata=dict(segment.metadata)))
    return merged


def chunk_segments(
    segments: list[Document],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Document]:
    """
    Découpe les segments d'UN document en chunks.

    Les chunks ne franchissent jamais une frontière de segment : un chunk
    appartient à une seule page (PDF) ou une seule section (DOCX).

    Raises:
        ValueError : si chunk_overlap >= chunk_size.
    """
    settings      = get_settings()
    chunk_size    = chunk_size or settings.chunk_size_chars
    chunk_overlap = settings.chunk_overlap_chars if chunk_overlap is None else chunk_overlap

    if chunk_overlap >= chunk_size:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) doit être < chunk_size ({chunk_size})."
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
        is_separator_regex=False,
    )

    chunks: list[Document] = []
    for segment in _merge_small_sections(segments, chunk_size):
        for chunk_text in splitter.split_text(segment.page_content):
            chunk_text = chunk_text.strip()
            if len(chunk_text) >= _MIN_CHUNK_CHARS:
                chunks.append(Document(page_content=chunk_text, metadata=dict(segment.metadata)))

    total = len(chunks)
    for idx, chunk in enumerate(chunks):
        source = chunk.metadata.get("source", "doc")
        chunk.metadata.update({
            "chunk_index": idx,
            "chunk_total": total,
            "chunk_id":    _sanitize_chunk_id(f"{source}__chunk_{idx:04d}"),
        })

    return chunks


def print_chunk_stats(chunks: list[Document]) -> None:
    """Affiche des statistiques descriptives sur les chunks produits."""
    if not chunks:
        logger.info("Aucun chunk à analyser.")
        return

    sizes = [len(c.page_content) for c in chunks]
    total = len(sizes)
    avg   = sum(sizes) / total

    by_module: dict[str, int] = {}
    for chunk in chunks:
        module = chunk.metadata.get("module") or "(sans module)"
        by_module[module] = by_module.get(module, 0) + 1

    logger.info("Statistiques des chunks :")
    logger.info("  Total    : %d", total)
    logger.info("  Moyenne  : %.0f chars", avg)
    logger.info("  Min/Max  : %d / %d chars", min(sizes), max(sizes))
    logger.info("  Par module BeHave :")
    for module, count in sorted(by_module.items()):
        bar = "█" * max(1, count * 20 // total)
        logger.info("    • %-35s %3d chunks  %s", module, count, bar)
