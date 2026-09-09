"""
boot_check.py  —  the skeleton's smoke test.

Its ONLY job: prove the empty machine is wired correctly. It checks four things,
in order, and prints a clear PASS/FAIL for each:

    1. Can the app READ config/rag.yaml?          (config is reachable + valid)
    2. Can the app REACH the db box + is pgvector usable?   (vector store alive)
    3. Can the app REACH the ollama box?          (AI brain alive)
    4. Do the eval thresholds match PRODUCT.md's promise?   (sanity)

No RAG logic here. If all four pass, the foundation is solid and we can start
laying real code on top in the next box.

WHY a smoke test at all: a skeleton that "looks right" but silently can't reach
the DB wastes hours later. We prove the plumbing works BEFORE anything depends
on it. Same instinct as a health endpoint in any backend service.
"""

from __future__ import annotations

import os
import sys
import time

import httpx
import psycopg
import yaml


# ANSI colors for a readable report (fall back to plain if not a TTY).
def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text


OK = _c("PASS", "32")
BAD = _c("FAIL", "31")


def _env(name: str, default: str | None = None) -> str:
    """Read an env var with an optional default, failing with a CLEAR message.

    A bare os.environ['X'] raises KeyError('X') three frames deep — useless in a
    boot log. This names the missing var and where to set it. (Step 1 principle:
    fail loudly at the boundary with a message you can act on.)
    """
    val = os.environ.get(name, default)
    if val is None or val == "":
        raise RuntimeError(f"required env var {name!r} is missing/empty — set it in .env")
    return val


def check_config() -> dict:
    """1. Read and parse config/rag.yaml. Returns the parsed dict."""
    with open("config/rag.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # Touch a few keys so a malformed file fails loudly HERE, not deep in the app.
    assert cfg["retrieval"]["mode"] in {"naive", "hybrid", "crag", "graph", "agentic"}
    assert cfg["embeddings"]["dimension"] > 0
    print(f"[{OK}] config/rag.yaml read — retrieval.mode = {cfg['retrieval']['mode']!r}, "
          f"embeddings.dimension = {cfg['embeddings']['dimension']}")
    return cfg


def check_db() -> None:
    """2. Connect to Postgres and confirm the pgvector extension is usable."""
    dsn = (
        f"host={_env('POSTGRES_HOST', 'db')} "
        f"port={_env('POSTGRES_PORT', '5432')} "
        f"user={_env('POSTGRES_USER', 'rag')} "
        f"password={_env('POSTGRES_PASSWORD')} "
        f"dbname={_env('POSTGRES_DB', 'rag_lab')}"
    )
    with psycopg.connect(dsn, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            # Enabling the extension is idempotent; this is where a plain Postgres
            # image (without pgvector) would fail — proving we have the right box.
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            conn.commit()
            cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
            version = cur.fetchone()[0]
    print(f"[{OK}] db reachable + pgvector enabled — vector extension v{version}")


def check_ollama() -> None:
    """3. Reach the ollama box's API. (Having zero models pulled yet is fine.)"""
    base = _env("OLLAMA_BASE_URL", "http://ollama:11434")
    resp = httpx.get(f"{base}/api/tags", timeout=10.0)
    resp.raise_for_status()
    models = resp.json().get("models", [])
    note = f"{len(models)} model(s) pulled" if models else "no models pulled yet (expected)"
    print(f"[{OK}] ollama reachable at {base} — {note}")


def check_eval_targets(cfg: dict) -> None:
    """4. Sanity: the finish-line numbers exist and are in a sane range."""
    t = cfg["evals"]["thresholds"]
    assert 0 < t["faithfulness"] <= 1
    assert 0 < t["recall_at_5"] <= 1
    assert t["p95_latency_seconds"] > 0
    print(f"[{OK}] eval targets present — faithfulness>={t['faithfulness']}, "
          f"recall@5>={t['recall_at_5']}, p95<={t['p95_latency_seconds']}s")


def main() -> int:
    print("=" * 70)
    print("RAG Lab — skeleton boot check")
    print("=" * 70)

    failures = 0
    cfg = None

    # Run config first (others may need it).
    try:
        cfg = check_config()
    except Exception as e:  # noqa: BLE001 — top-level reporter, we want everything
        print(f"[{BAD}] config/rag.yaml — {type(e).__name__}: {e}")
        failures += 1

    # DB + Ollama can be slow to accept connections right after `up`; retry briefly.
    for name, fn in (("db", check_db), ("ollama", check_ollama)):
        for attempt in range(5):
            try:
                fn()
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 4:
                    print(f"[{BAD}] {name} — {type(e).__name__}: {e}")
                    failures += 1
                else:
                    time.sleep(2)

    if cfg is not None:
        try:
            check_eval_targets(cfg)
        except Exception as e:  # noqa: BLE001
            print(f"[{BAD}] eval targets — {type(e).__name__}: {e}")
            failures += 1

    print("-" * 70)
    if failures == 0:
        print(f"{_c('ALL CHECKS PASSED', '32')} — skeleton is solid. Ready for the next box.")
        # Keep the container alive so `docker compose up` stays up for inspection.
        print("(app box will now idle; Ctrl-C or `docker compose down` to stop.)")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return 0
        return 0
    else:
        print(f"{_c(f'{failures} CHECK(S) FAILED', '31')} — fix the wiring above before building on it.")
        return 1


if __name__ == "__main__":
    sys.exit(main())