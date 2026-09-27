"""
run_indexation.py
=================
Script d'indexation offline.

Orchestre les 3 étapes :
  1. CHARGEMENT  : lecture des DOCX/PDF/TXT de data/documents/ (documentation
                   officielle) et data/uploaded_docs/ (uploads admin), avec
                   module et titre déclarés dans le manifeste
  2. CHUNKING    : découpage par page (PDF) / section (DOCX)
  3. EMBEDDING   : vecteurs + stockage persistant dans ChromaDB

À exécuter UNE SEULE FOIS (ou à chaque mise à jour des documents), depuis la
racine du projet :
    python -m ingestion.run_indexation [--reset]

--reset est obligatoire après un changement de modèle d'embedding.
"""

import sys
import time
import logging
import argparse

from config import get_settings
from ingestion.chunker import print_chunk_stats
from ingestion.document_loader import Document, list_document_files
from ingestion.embedder import BeHaveVectorStore
from ingestion.manifest import load_manifest
from ingestion.pipeline import build_chunks


DOCUMENT_DIRS = [get_settings().documents_dir, get_settings().uploaded_docs_dir]
CHROMA_DB_DIR = get_settings().chroma_db_dir

logger = logging.getLogger("run_indexation")


def run_indexation(reset: bool = False) -> BeHaveVectorStore:
    """Exécute le pipeline complet d'indexation et retourne le store alimenté."""
    start_time = time.perf_counter()

    _print_header()
    logger.info("Démarrage du pipeline d'indexation (reset=%s)", reset)

    for directory in DOCUMENT_DIRS:
        print(f"  Documents source : {directory}")
    print(f"  Manifeste        : {get_settings().manifest_path}")
    print(f"  Base vectorielle : {CHROMA_DB_DIR}\n")

    _print_step(1, "Chargement des documents et découpage en chunks")

    files = list_document_files(DOCUMENT_DIRS)
    if not files:
        logger.error("Aucun fichier PDF/DOCX/TXT dans %s", DOCUMENT_DIRS)
        print("\n  ✗ Aucun document trouvé.")
        sys.exit(1)

    manifest = load_manifest(get_settings().manifest_path)
    chunks: list[Document] = []
    n_documents = 0

    for file_path in files:
        try:
            file_chunks = build_chunks(file_path, manifest)
        except Exception as exc:
            logger.error("Erreur sur %s : %s", file_path.name, exc)
            continue
        if not file_chunks:
            logger.warning("Ignoré (aucun texte extractible) : %s", file_path.name)
            continue
        if file_path.name not in manifest:
            logger.warning("Absent du manifeste (module non renseigné) : %s", file_path.name)

        n_documents += 1
        chunks.extend(file_chunks)
        logger.info(
            "  ✓ %s → %d chunks | module=%s",
            file_path.name, len(file_chunks), file_chunks[0].metadata.get("module"),
        )

    if not chunks:
        logger.error("Aucun chunk produit — vérifiez le contenu des documents.")
        print("\n  ✗ Aucun chunk produit.")
        sys.exit(1)

    print(f"\n  ✓ {n_documents} document(s) chargé(s)")
    print_chunk_stats(chunks)

    _print_step(2, "Préparation de la base vectorielle")

    store = BeHaveVectorStore(persist_directory=CHROMA_DB_DIR)

    if reset:
        print("  Mode RESET : vidage de la collection...")
        store.clear_collection(confirm=True)
    elif not store.is_compatible:
        logger.error(
            "Index construit avec '%s', modèle configuré '%s' : relancez avec --reset.",
            store.indexed_with, store.embedding_model_name,
        )
        sys.exit(1)

    _print_step(3, "Génération des embeddings et stockage ChromaDB")

    nb_indexed = store.add_documents(chunks)

    elapsed = time.perf_counter() - start_time
    _print_summary(n_documents, len(chunks), nb_indexed, elapsed)
    _run_smoke_test(store)

    return store


def _run_smoke_test(store: BeHaveVectorStore) -> None:
    """
    Vérifie que la base indexée répond à une requête simple (recherche
    vectorielle seule) et signale les scores sous le seuil cosinus.
    """
    TEST_QUERY = "What is BeHave?"
    MIN_SCORE  = get_settings().rag_min_cosine_similarity
    EXPECTED_K = 3

    print("\n  Vérification — Test de recherche :")
    print(f"  Requête : {TEST_QUERY!r}\n")

    results = store.search(TEST_QUERY, k=EXPECTED_K)

    if not results:
        logger.warning("Test de fumée : aucun résultat retourné.")
        print("  ⚠ Aucun résultat — base peut-être vide ?")
        return

    all_ok = True
    for i, doc in enumerate(results):
        score  = doc.metadata.get("similarity_score", 0)
        module = doc.metadata.get("module", "?")
        source = doc.metadata.get("source", "?")
        status = "✓" if score >= MIN_SCORE else "⚠"

        if score < MIN_SCORE:
            all_ok = False

        preview = doc.page_content[:100].replace("\n", " ")
        print(f"  [{i + 1}] {status} score={score:.4f} | {module} ({source})")
        print(f"      {preview}...")

    if all_ok:
        print("\n  ✓ Test de fumée réussi — pipeline opérationnel !")
        logger.info("Test de fumée réussi (%d résultats, score min %.4f)",
                    len(results), min(d.metadata.get("similarity_score", 0) for d in results))
    else:
        print(f"\n  ⚠ Certains scores sont inférieurs au seuil ({MIN_SCORE}).")
        print("    Vérifiez la qualité des documents et le manifeste.")
        logger.warning("Test de fumée : scores faibles détectés.")


def _print_header() -> None:
    print("=" * 65)
    print("  BeHave AI Chatbot — Pipeline d'Indexation")
    print("=" * 65)


def _print_step(n: int, label: str) -> None:
    print(f"\n{'─' * 65}")
    print(f"  ÉTAPE {n}/3 — {label}")
    print(f"{'─' * 65}")


def _print_summary(
    n_docs: int,
    n_chunks: int,
    n_indexed: int,
    elapsed: float,
) -> None:
    print(f"\n{'=' * 65}")
    print("  INDEXATION TERMINÉE")
    print(f"{'=' * 65}")
    print(f"    Documents traités  : {n_docs}")
    print(f"    Chunks produits    : {n_chunks}")
    print(f"    Chunks indexés     : {n_indexed}")
    print(f"    Durée totale       : {elapsed:.1f}s")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline d'indexation BeHave AI Chatbot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            "  python -m ingestion.run_indexation\n"
            "  python -m ingestion.run_indexation --reset\n"
        ),
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Vider la base ChromaDB avant l'indexation (ré-indexation complète).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    args = _parse_args()
    try:
        run_indexation(reset=args.reset)
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n  Indexation interrompue par l'utilisateur.")
        logger.info("Indexation interrompue (KeyboardInterrupt).")
        sys.exit(1)