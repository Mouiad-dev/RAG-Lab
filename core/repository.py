"""
core/repository.py  —  data access for documents + chunks (the Repository layer).

Keeps ALL SQL in one place. The service orchestrates; the repository talks to the
DB. Callers never write SQL. This is the boundary that lets us swap pgvector for
Qdrant later without touching business logic.

Write path only for now (store an ingested doc). The read/search path lands in the
retrieval box next.

Performance: chunks are inserted with executemany (one round-trip for the batch),
not a loop of single INSERTs — the ORM-N+1 equivalent we avoid. pgvector accepts a
vector as the string '[0.1,0.2,...]'.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg

from ingestion.types import Chunk


def _vec_literal(vector: list[float]) -> str:
    """pgvector text input format: '[f1,f2,...]'. Compact, no spaces."""
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


@dataclass
class StoredDocument:
    document_id: int
    chunk_count: int


class DocumentRepository:
    """All reads/writes for documents + chunks live here."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def apply_schema(self, schema_sql: str) -> None:
        """Run the idempotent schema DDL (safe to call on every startup)."""
        with self.conn.cursor() as cur:
            cur.execute(schema_sql)
        self.conn.commit()

    def store(
        self,
        source_filename: str,
        doc_type: str,
        extractor_name: str,
        page_count: int,
        chunks: list[Chunk],
    ) -> StoredDocument:
        """Insert one document and all its (already-embedded) chunks atomically.

        Every chunk MUST already have .embedding set (the embed step runs before
        this). We assert that rather than silently storing NULLs.
        """
        if not chunks:
            raise ValueError(f"refusing to store '{source_filename}' with 0 chunks")
        for c in chunks:
            if c.embedding is None:
                raise ValueError(
                    f"chunk {c.chunk_index} of '{source_filename}' has no embedding — "
                    f"run the embed step before storing."
                )

        with self.conn.cursor() as cur:
            # 1) upsert-ish: insert the document, get its id.
            cur.execute(
                """
                INSERT INTO documents (source_filename, doc_type, extractor_name, page_count)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (source_filename) DO UPDATE
                    SET doc_type = EXCLUDED.doc_type,
                        extractor_name = EXCLUDED.extractor_name,
                        page_count = EXCLUDED.page_count
                RETURNING id;
                """,
                (source_filename, doc_type, extractor_name, page_count),
            )
            document_id = cur.fetchone()[0]

            # 2) clear any previous chunks for this doc (clean re-ingest).
            cur.execute("DELETE FROM chunks WHERE document_id = %s;", (document_id,))

            # 3) batch-insert all chunks in ONE round-trip (no N+1).
            cur.executemany(
                """
                INSERT INTO chunks (document_id, chunk_index, text, page_number, embedding)
                VALUES (%s, %s, %s, %s, %s);
                """,
                [
                    (document_id, c.chunk_index, c.text, c.page_number, _vec_literal(c.embedding))
                    for c in chunks
                ],
            )
        self.conn.commit()
        return StoredDocument(document_id=document_id, chunk_count=len(chunks))