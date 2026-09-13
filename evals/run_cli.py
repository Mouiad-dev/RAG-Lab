"""
evals/run_cli.py  —  press the button on the lab: run the golden set, print numbers.

The EvalRunner (runner.py) knew HOW to score a config, but nothing ran it from the
command line. This is that missing "run the exam" step. It:

    1. loads config/rag.yaml + the golden set,
    2. connects to the db box and builds the SAME embedder used at ingest time,
    3. runs the golden set once PER mode you ask for (default: naive then hybrid),
    4. prints one comparison table + a pass/fail check against PRODUCT.md targets.

The whole point of the lab in one command:
    docker compose exec app python -m evals.run_cli --modes naive hybrid
    -> "recall@5: naive 0.70 -> hybrid 0.90"  (a measured sentence, not a vibe)

Retrieval-only by default (recall@k + latency), which needs NO LLM, so it's fast
and free. Answer-quality metrics (faithfulness/relevance) come later once the
LLM-judge path is wired through this CLI.
"""

from __future__ import annotations

import argparse
import copy
import os
import sys
from pathlib import Path

import psycopg
import yaml

from core.repository import DocumentRepository
from embeddings.embedder import OllamaEmbedder
from evals.runner import EvalRunner, Scorecard, load_golden_set

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "rag.yaml"


def _dsn() -> str:
    return (
        f"host={os.environ.get('POSTGRES_HOST', 'db')} "
        f"port={os.environ.get('POSTGRES_PORT', '5432')} "
        f"user={os.environ.get('POSTGRES_USER', 'rag')} "
        f"password={os.environ.get('POSTGRES_PASSWORD', '')} "
        f"dbname={os.environ.get('POSTGRES_DB', 'rag_lab')}"
    )


def _run_mode(
    base_cfg: dict,
    mode: str,
    repo: DocumentRepository,
    embedder: OllamaEmbedder,
    golden: list,
    top_k: int,
    rerank: bool,
) -> Scorecard:
    """Run the golden set for ONE retrieval mode and return its scorecard."""
    cfg = copy.deepcopy(base_cfg)
    cfg.setdefault("retrieval", {})["mode"] = mode
    cfg["retrieval"].setdefault("rerank", {})["enabled"] = rerank
    return EvalRunner(cfg, repo, embedder).run(golden, top_k=top_k)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the golden set across retrieval modes.")
    parser.add_argument(
        "--modes", nargs="+", default=["naive", "hybrid"],
        help="retrieval modes to compare, in order (default: naive hybrid)",
    )
    parser.add_argument("--top-k", type=int, default=None,
                        help="chunks to retrieve (default: retrieval.top_k from rag.yaml)")
    parser.add_argument("--rerank", action="store_true",
                        help="wrap each mode in the cross-encoder reranker")
    args = parser.parse_args()

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    top_k = args.top_k if args.top_k is not None else cfg.get("retrieval", {}).get("top_k", 5)
    thresholds = cfg.get("evals", {}).get("thresholds", {})
    golden_path = cfg.get("evals", {}).get("golden_set_path", "evals/golden_set.jsonl")

    golden = load_golden_set(BASE_DIR / golden_path)
    if not golden:
        print(f"[eval] golden set is empty: {golden_path}", file=sys.stderr)
        return 2

    embedder = OllamaEmbedder.from_yaml(cfg)

    print("=" * 74)
    print(f"RAG Lab eval — {len(golden)} golden questions, top_k={top_k}, "
          f"rerank={'on' if args.rerank else 'off'}")
    print("=" * 74)

    cards: list[Scorecard] = []
    with psycopg.connect(_dsn(), connect_timeout=15) as conn:
        repo = DocumentRepository(conn)
        for mode in args.modes:
            try:
                cards.append(_run_mode(cfg, mode, repo, embedder, golden, top_k, args.rerank))
            except Exception as e:  # one bad mode shouldn't kill the whole comparison
                print(f"[eval] mode {mode!r} FAILED: {type(e).__name__}: {e}", file=sys.stderr)

    if not cards:
        return 1

    # ---- the comparison table ----
    recall_target = thresholds.get("recall_at_5", 0.90)
    p95_target = thresholds.get("p95_latency_seconds", 5.0)
    print(f"\n{'mode':<16}{'n':>4}{'recall@k':>11}{'p95(s)':>10}{'mean(s)':>10}{'  recall>=%.2f?' % recall_target}")
    print("-" * 74)
    for c in cards:
        ok = "PASS" if c.recall_at_k >= recall_target else "FAIL"
        print(f"{c.mode:<16}{c.n:>4}{c.recall_at_k:>11.3f}{c.p95_latency_s:>10.3f}"
              f"{c.mean_latency_s:>10.3f}{ok:>14}")

    # ---- the headline delta (what you say in an interview) ----
    if len(cards) >= 2:
        a, b = cards[0], cards[-1]
        print("-" * 74)
        print(f"delta  recall@k: {a.mode} {a.recall_at_k:.3f} -> {b.mode} {b.recall_at_k:.3f} "
              f"({b.recall_at_k - a.recall_at_k:+.3f})")

    # ---- per-language breakdown (bilingual corpus sanity) ----
    print("\nper-language recall@k:")
    for c in cards:
        by_lang: dict[str, list[float]] = {}
        for row in c.per_question:
            by_lang.setdefault(row["lang"], []).append(row["recall"])
        parts = [f"{lang}={sum(v)/len(v):.3f}(n={len(v)})" for lang, v in sorted(by_lang.items())]
        print(f"  {c.mode:<16} " + "  ".join(parts))

    return 0


if __name__ == "__main__":
    sys.exit(main())
