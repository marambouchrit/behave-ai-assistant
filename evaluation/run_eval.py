"""
run_eval.py
===========
Évaluation du retrieval BeHave sur le jeu evaluation/eval_set.yaml.

Compare, sur les mêmes candidats du premier étage (recherche vectorielle) :
  - "cosine"  : classement par similarité cosinus seule (sans reranker)
  - un ou plusieurs rerankers (cross-encoders)

Métriques, pour chaque configuration :
  Qualité du classement (questions dans le périmètre)
    doc@1, doc@k : le bon document est en 1re position / dans les k premiers
    loc@k        : un chunk au bon emplacement (section ou page) est dans les k
    MRR@k        : rang moyen réciproque du premier chunk bien placé
  Décision hors périmètre (meilleur score de chaque question)
    AUC          : probabilité qu'une question du périmètre obtienne un
                   meilleur score qu'une question hors périmètre (1.0 = parfait)
    seuil        : seuil qui maximise l'exactitude équilibrée (TPR + TNR) / 2
    TPR / TNR    : questions du périmètre acceptées / hors périmètre rejetées
    bout-en-bout : loc@k en comptant comme échec une question rejetée à tort
  Latence
    ms/question du reranking (moyenne, p95), sur CPU

Usage (depuis la racine du projet) :
    python -m evaluation.run_eval                       # cosine + reranker configuré
    python -m evaluation.run_eval --rerankers mmarco bge
    python -m evaluation.run_eval --output evaluation/results.md
"""

import argparse
import logging
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from config import get_settings
from ingestion.document_loader import Document
from ingestion.embedder import BeHaveVectorStore
from rag.reranker import Reranker

logger = logging.getLogger("run_eval")

EVAL_SET_PATH = Path(__file__).parent / "eval_set.yaml"
# Notes rédigées à la main (décisions, justifications), recopiées dans le
# rapport généré pour survivre à chaque régénération.
NOTES_PATH    = Path(__file__).parent / "notes.md"

RERANKER_ALIASES: dict[str, str] = {
    "mmarco": "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
    "bge":    "BAAI/bge-reranker-v2-m3",
}


# ─── Jeu d'évaluation ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ExpectedLocation:
    document: str
    sections: tuple[str, ...] = ()
    pages:    tuple[int, ...] = ()

    def matches(self, chunk: Document) -> bool:
        meta = chunk.metadata
        if meta.get("source") != self.document:
            return False
        if not self.sections and not self.pages:
            return True
        section = (meta.get("section") or "").lower()
        return (
            any(s.lower() in section for s in self.sections)
            or meta.get("page") in self.pages
        )


@dataclass(frozen=True)
class EvalQuestion:
    id:       str
    question: str
    in_scope: bool
    kind:     str | None = None
    expected: tuple[ExpectedLocation, ...] = ()

    def doc_match(self, chunk: Document) -> bool:
        return any(chunk.metadata.get("source") == e.document for e in self.expected)

    def loc_match(self, chunk: Document) -> bool:
        return any(e.matches(chunk) for e in self.expected)


def load_eval_set(path: Path) -> list[EvalQuestion]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = []
    for item in raw["questions"]:
        expected = tuple(
            ExpectedLocation(
                document=e["document"],
                sections=tuple(e.get("sections") or ()),
                pages=tuple(e.get("pages") or ()),
            )
            for e in item.get("expected") or ()
        )
        if item["in_scope"] and not expected:
            raise ValueError(f"{item['id']} : 'expected' requis pour une question du périmètre.")
        questions.append(EvalQuestion(
            id=item["id"], question=item["question"], in_scope=item["in_scope"],
            kind=item.get("kind"), expected=expected,
        ))
    return questions


# ─── Métriques ────────────────────────────────────────────────────────────────

@dataclass
class ConfigResult:
    name:      str
    k:         int
    rankings:  dict[str, list[tuple[Document, float]]] = field(default_factory=dict)
    latencies: list[float] = field(default_factory=list)


def _first_loc_rank(q: EvalQuestion, ranked: list[tuple[Document, float]], k: int) -> int | None:
    for rank, (chunk, _) in enumerate(ranked[:k], start=1):
        if q.loc_match(chunk):
            return rank
    return None


def _auc(positives: list[float], negatives: list[float]) -> float:
    if not positives or not negatives:
        return float("nan")
    wins = sum(
        1.0 if p > n else 0.5 if p == n else 0.0
        for p in positives for n in negatives
    )
    return wins / (len(positives) * len(negatives))


def _best_threshold(in_scores: list[float], out_scores: list[float]) -> tuple[float, float, float]:
    """Seuil (accepter si score >= seuil) maximisant (TPR + TNR) / 2 ; à égalité, le TPR."""
    best = (float("-inf"), -1.0, -1.0, 0.0)  # (balanced, tpr, -threshold, threshold)
    for t in sorted(set(in_scores + out_scores)):
        tpr = sum(s >= t for s in in_scores) / len(in_scores)
        tnr = sum(s < t for s in out_scores) / len(out_scores)
        candidate = ((tpr + tnr) / 2, tpr, -t, t)
        if candidate > best:
            best = candidate
    _, tpr, _, threshold = best
    tnr = sum(s < threshold for s in out_scores) / len(out_scores)
    return threshold, tpr, tnr


def summarize(result: ConfigResult, questions: list[EvalQuestion], threshold: float | None) -> dict:
    k = result.k
    in_q  = [q for q in questions if q.in_scope]
    out_q = [q for q in questions if not q.in_scope]
    top   = {q.id: (result.rankings[q.id][0][1] if result.rankings[q.id] else float("-inf")) for q in questions}

    doc1 = sum(bool(result.rankings[q.id]) and q.doc_match(result.rankings[q.id][0][0]) for q in in_q)
    dock = sum(any(q.doc_match(c) for c, _ in result.rankings[q.id][:k]) for q in in_q)
    ranks = {q.id: _first_loc_rank(q, result.rankings[q.id], k) for q in in_q}
    lock = sum(r is not None for r in ranks.values())
    mrr  = sum(1 / r for r in ranks.values() if r) / len(in_q)

    in_scores  = [top[q.id] for q in in_q]
    out_scores = [top[q.id] for q in out_q]
    hard_scores = [top[q.id] for q in out_q if q.kind == "hard"]

    tuned_t, _, _ = _best_threshold(in_scores, out_scores)
    t = tuned_t if threshold is None else threshold
    accepted = {q.id for q in questions if top[q.id] >= t}

    return {
        "name":        result.name,
        "doc@1":       doc1 / len(in_q),
        f"doc@{k}":    dock / len(in_q),
        f"loc@{k}":    lock / len(in_q),
        f"MRR@{k}":    mrr,
        "AUC":         _auc(in_scores, out_scores),
        "AUC (hard)":  _auc(in_scores, hard_scores),
        "seuil":       t,
        "seuil optimal": tuned_t,
        "TPR":         sum(q.id in accepted for q in in_q) / len(in_q),
        "TNR":         sum(q.id not in accepted for q in out_q) / len(out_q),
        "bout-en-bout": sum(ranks[q.id] is not None and q.id in accepted for q in in_q) / len(in_q),
        "ms/question": statistics.mean(result.latencies) if result.latencies else 0.0,
        "p95 ms":      _p95(result.latencies),
        "faux négatifs": sorted(q.id for q in in_q if q.id not in accepted),
        "faux positifs": sorted(q.id for q in out_q if q.id in accepted),
        "localisation manquée": sorted(q.id for q in in_q if ranks[q.id] is None),
        "scores": {q.id: top[q.id] for q in questions},
    }


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]


# ─── Exécution ────────────────────────────────────────────────────────────────

def run(reranker_names: list[str], k: int, candidates_k: int) -> tuple[list[EvalQuestion], list[ConfigResult], dict]:
    questions = load_eval_set(EVAL_SET_PATH)
    store     = BeHaveVectorStore()
    store.ensure_compatible()

    logger.info("Premier étage : recherche vectorielle top-%d pour %d questions", candidates_k, len(questions))
    candidates: dict[str, list[Document]] = {}
    search_ms: list[float] = []
    for q in questions:
        start = time.perf_counter()
        candidates[q.id] = store.search(q.question, k=candidates_k)
        search_ms.append((time.perf_counter() - start) * 1000)

    cosine = ConfigResult(name="cosine (sans reranker)", k=k)
    for q in questions:
        cosine.rankings[q.id] = [(c, c.metadata["similarity_score"]) for c in candidates[q.id]]
    results = [cosine]

    for name in reranker_names:
        model_name = RERANKER_ALIASES.get(name, name)
        reranker   = Reranker(model_name)
        result     = ConfigResult(name=model_name, k=k)
        reranker.score(questions[0].question, candidates[questions[0].id][:2])  # préchauffage
        for q in questions:
            start  = time.perf_counter()
            scores = reranker.score(q.question, candidates[q.id])
            result.latencies.append((time.perf_counter() - start) * 1000)
            result.rankings[q.id] = sorted(zip(candidates[q.id], scores), key=lambda p: p[1], reverse=True)
        results.append(result)

    context = {
        "embedding_model": store.embedding_model_name,
        "chunks":          store.get_collection_info()["document_count"],
        "search_ms":       statistics.mean(search_ms),
    }
    return questions, results, context


def _fmt(value) -> str:
    if isinstance(value, float):
        return f"{value:.3f}" if abs(value) < 10 else f"{value:.0f}"
    return str(value)


def render_markdown(
    questions: list[EvalQuestion],
    summaries: list[dict],
    context: dict,
    k: int,
    candidates_k: int,
) -> str:
    n_in  = sum(q.in_scope for q in questions)
    n_out = len(questions) - n_in
    n_hard = sum(q.kind == "hard" for q in questions)
    columns = ["doc@1", f"doc@{k}", f"loc@{k}", f"MRR@{k}", "AUC", "AUC (hard)",
               "seuil optimal", "seuil", "TPR", "TNR", "bout-en-bout", "ms/question", "p95 ms"]

    lines = [
        "# Évaluation du retrieval BeHave",
        "",
        f"Généré le {date.today().isoformat()} par `python -m evaluation.run_eval`.",
        "",
        f"- Jeu : {len(questions)} questions ({n_in} dans le périmètre, {n_out} hors périmètre dont {n_hard} de domaine proche)",
        f"- Index : {context['chunks']} chunks, embeddings `{context['embedding_model']}`",
        f"- Premier étage : top-{candidates_k} vectoriel ({context['search_ms']:.0f} ms/question) ; k = {k} chunks transmis au LLM",
        "- Latences mesurées sur CPU",
        "",
        "| Configuration | " + " | ".join(columns) + " |",
        "|---|" + "---|" * len(columns),
    ]
    for s in summaries:
        lines.append(f"| {s['name']} | " + " | ".join(_fmt(s[c]) for c in columns) + " |")

    if NOTES_PATH.exists():
        lines += ["", NOTES_PATH.read_text(encoding="utf-8").strip()]

    lines += ["", "## Erreurs au seuil retenu", ""]
    for s in summaries:
        lines.append(f"**{s['name']}** (seuil {s['seuil']:.3f})")
        lines.append(f"- faux négatifs (question BeHave rejetée) : {', '.join(s['faux négatifs']) or 'aucun'}")
        lines.append(f"- faux positifs (hors sujet accepté) : {', '.join(s['faux positifs']) or 'aucun'}")
        lines.append(f"- localisation manquée dans le top-{k} : {', '.join(s['localisation manquée']) or 'aucune'}")
        lines.append("")

    lines += [
        "## Annexe : meilleur score par question",
        "",
        "Trié par score du dernier modèle ; ✗ = hors périmètre.",
        "",
        "| Question | " + " | ".join(s["name"] for s in summaries) + " |",
        "|---|" + "---|" * len(summaries),
    ]
    by_id = {q.id: q for q in questions}
    for qid in sorted(by_id, key=lambda i: summaries[-1]["scores"][i], reverse=True):
        mark = "" if by_id[qid].in_scope else " ✗"
        lines.append(
            f"| {qid}{mark} | " + " | ".join(f"{s['scores'][qid]:.3f}" for s in summaries) + " |"
        )
    lines.append("")

    lines += [
        "## Lecture",
        "",
        f"- **doc@k / loc@k / MRR@k** : qualité du classement sur les {n_in} questions du périmètre.",
        "- **AUC** : séparation entre questions du périmètre et hors périmètre par le meilleur score "
        "(1.0 = un seuil peut tout séparer). **AUC (hard)** : idem contre les seules questions de domaine proche.",
        "- **seuil optimal** : seuil maximisant (TPR + TNR) / 2 sur ce jeu. **seuil** : seuil appliqué "
        "(configuré avec `--use-configured-thresholds`, sinon l'optimal).",
        "- **TPR / TNR** : questions du périmètre acceptées / hors périmètre rejetées au seuil appliqué.",
        "- **bout-en-bout** : question du périmètre acceptée ET bon emplacement dans le top-k.",
        "- Jeu de petite taille : les écarts de quelques points ne sont pas significatifs.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Évaluation du retrieval BeHave")
    parser.add_argument(
        "--rerankers", nargs="*", default=[settings.reranker_model],
        help=f"alias ({', '.join(RERANKER_ALIASES)}) ou noms de modèles ; vide = cosine seul",
    )
    parser.add_argument("--k", type=int, default=settings.rag_k)
    parser.add_argument("--candidates", type=int, default=settings.rag_candidates_k)
    parser.add_argument(
        "--use-configured-thresholds", action="store_true",
        help="applique les seuils de config.py au lieu du seuil optimal sur ce jeu",
    )
    parser.add_argument("--output", type=Path, help="fichier Markdown de résultats")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "sentence_transformers", "ingestion.embedder"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    questions, results, context = run(args.rerankers, args.k, args.candidates)

    summaries = []
    for result in results:
        threshold = None
        if args.use_configured_thresholds:
            threshold = (
                settings.rag_min_cosine_similarity if not result.latencies
                else settings.rag_min_rerank_score
            )
        summaries.append(summarize(result, questions, threshold))

    report = render_markdown(questions, summaries, context, args.k, args.candidates)
    sys.stdout.reconfigure(encoding="utf-8")
    print(report)
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        logger.info("Résultats écrits dans %s", args.output)


if __name__ == "__main__":
    main()
