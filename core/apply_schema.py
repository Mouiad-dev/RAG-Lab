"""
core/apply_schema.py  —  apply the pgvector schema (idempotent) at startup.

Separate from boot_check.py on purpose: boot_check ASKS "is the plumbing wired?"
(a diagnostic); this one DOES "make sure the tables exist" (a setup step). The
schema DDL is CREATE ... IF NOT EXISTS, so running this on every boot is safe.

Run:  python -m core.apply_schema
Used by the app container's startup before `runserver`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg

from core.repository import DocumentRepository

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def _dsn() -> str:
    return (
        f"host={os.environ.get('POSTGRES_HOST', 'db')} "
        f"port={os.environ.get('POSTGRES_PORT', '5432')} "
        f"user={os.environ.get('POSTGRES_USER', 'rag')} "
        f"password={os.environ.get('POSTGRES_PASSWORD', '')} "
        f"dbname={os.environ.get('POSTGRES_DB', 'rag_lab')}"
    )


def main() -> int:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg.connect(_dsn(), connect_timeout=15) as conn:
        DocumentRepository(conn).apply_schema(schema_sql)
    print(f"[schema] applied {SCHEMA_PATH.name} — documents + chunks ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
