"""
manifest.py
===========
Métadonnées déclarées par document : module BeHave et titre lisible.

Le module d'un document n'est jamais déduit de son nom de fichier : il est
déclaré dans un manifeste YAML (config : MANIFEST_PATH, défaut
data/manifest.yaml), clé = nom réel du fichier.

    documents:
      BeHave_Master_Data_User_Guide.docx:
        module: BeHave Master Data
        title: Guide utilisateur Master Data     # optionnel

Un document absent du manifeste est indexé avec module = None : il reste
interrogeable, mais aucune étiquette de module n'est affichée pour lui.
L'upload admin met à jour ce fichier (upsert_entry), si bien qu'un
`run_indexation --reset` retrouve les mêmes métadonnées.
"""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_write_lock = threading.Lock()


@dataclass(frozen=True)
class ManifestEntry:
    module: str | None = None
    title:  str | None = None


class ManifestError(ValueError):
    """Manifeste illisible ou mal structuré."""


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_manifest(path: Path) -> dict[str, ManifestEntry]:
    """
    Lit le manifeste. Fichier absent → manifeste vide (avertissement).

    Raises:
        ManifestError : YAML invalide ou structure inattendue.
    """
    if not path.exists():
        logger.warning("Manifeste introuvable (%s) : aucun module ne sera renseigné.", path)
        return {}

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ManifestError(f"Manifeste YAML invalide ({path}) : {exc}") from exc

    documents = raw.get("documents") or {}
    if not isinstance(documents, dict):
        raise ManifestError(f"'documents' doit être un dictionnaire ({path}).")

    entries: dict[str, ManifestEntry] = {}
    for filename, fields in documents.items():
        fields = fields or {}
        if not isinstance(fields, dict):
            raise ManifestError(f"Entrée invalide pour '{filename}' ({path}).")
        entries[str(filename)] = ManifestEntry(
            module=_clean(fields.get("module")),
            title=_clean(fields.get("title")),
        )
    return entries


def upsert_entry(path: Path, filename: str, entry: ManifestEntry) -> None:
    """Ajoute ou remplace l'entrée d'un document dans le manifeste."""
    with _write_lock:
        raw: dict = {}
        if path.exists():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        documents = raw.setdefault("documents", {}) or {}
        raw["documents"] = documents

        documents[filename] = {
            key: value
            for key, value in (("module", entry.module), ("title", entry.title))
            if value
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(raw, allow_unicode=True, sort_keys=True),
            encoding="utf-8",
        )
    logger.info("Manifeste mis à jour : %s → %s", filename, entry)
