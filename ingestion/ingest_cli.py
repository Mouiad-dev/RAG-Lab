"""
ingestion/ingest_cli.py  —  ingest ONE file into pgvector, end to end.

The missing "press the button" step: all the ingestion pieces exist (router,
extractors, chunkers, embedder, repository) but nothing wired them into a single
runnable action. This does the whole Phase-A journey for one file:

    file --route--> extract --chunk--> embed (BGE-M3) --store--> pgvector

Run (inside the app container, where Ollama + the db box are reachable):
    docker compose exec app python -m ingestion.ingest_cli data/some.pdf

Or locally if you have Ollama + Postgres reachable via the env vars.

Prints a one-line summary so you can see exactly what was routed + stored.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
import yaml

from core.repository import DocumentRepository
from embeddings.embedder import OllamaEmbedder
from ingestion.service import IngestionConfig, IngestionService

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest one file into pgvector.")
    parser.add_argument("path", help="path to the file to ingest (pdf/png/jpg)")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"[ingest] file not found: {path}", file=sys.stderr)
        return 2

    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    # 1) route -> extract -> chunk
    service = IngestionService(IngestionConfig.from_yaml(cfg))
    result = service.ingest(path)
    print(f"[ingest] {result.summary}")

    if not result.chunks:
        print("[ingest] 0 chunks produced — nothing to store (empty/undreadable doc?).",
              file=sys.stderr)
        return 1

    # 2) embed every chunk with the SAME embedder used at query time (BGE-M3)
    embedder = OllamaEmbedder.from_yaml(cfg)
    service.embed_chunks(result.chunks, embedder)

    # 3) store the document + its embedded chunks atomically
    with psycopg.connect(_dsn(), connect_timeout=15) as conn:
        stored = DocumentRepository(conn).store(
            source_filename=result.doc.source_filename,
            doc_type=result.doc.doc_type,
            extractor_name=result.doc.extractor_name,
            page_count=result.doc.page_count,
            chunks=result.chunks,
        )
    print(f"[ingest] stored document id={stored.document_id} "
          f"with {stored.chunk_count} chunk(s). Ready for retrieval + eval.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
