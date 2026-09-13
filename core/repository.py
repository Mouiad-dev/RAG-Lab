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

import re
from dataclasses import dataclass

import psycopg

from ingestion.types import Chunk


def _vec_literal(vector: list[float]) -> str:
    """pgvector text input format: '[f1,f2,...]'. Compact, no spaces."""
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


# Common EN + AR function words. In an OR keyword query these match almost every
# chunk and drown the meaningful terms in noise (measured: they dragged hybrid
# BELOW naive). The 'simple' FTS config does no stopword removal, so we do a small
# one here. This is a poor-man's IDF: keep the rare, meaningful words; drop the
# ones that carry no retrieval signal. A real BM25 leg would weight by IDF instead.
_STOPWORDS = frozenset(
    """
    a an the this that these those of in on at to for from by with about as into
    is are was were be been being do does did done can could should would will
    what which who whom whose when where why how and or not no i you he she it we
    they me my your his her its our their there here have has had my mine
    من في على الى إلى عن مع هذا هذه ذلك التي الذي ما ماذا كيف اين أين متى لماذا
    هل و او أو ثم كان كانت يكون هو هي هم انا أنا نحن انت أنت لا نعم قد الى عند
    """.split()
)


def _keyword_terms(query_text: str) -> list[str]:
    """Query -> the meaningful lexemes for an OR tsquery (stopwords + 1-char dropped)."""
    words = re.findall(r"\w+", query_text.lower(), flags=re.UNICODE)
    return [w for w in words if len(w) > 1 and w not in _STOPWORDS]


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

    # ---- read path: vector similarity search --------------------------------
    def search_by_vector(
        self, query_vector: list[float], top_k: int
    ) -> list[tuple[str, str, int, int, float]]:
        """Return the top_k nearest chunks to query_vector by cosine distance.

        Returns rows of (text, source_filename, page_number, chunk_index, score)
        where score = 1 - cosine_distance, so HIGHER = more relevant (easier to
        reason about than raw distance). '<=>' is pgvector's cosine-distance op.

        The HNSW index on embedding makes this fast on large tables; without it
        this would scan every row.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.text,
                       d.source_filename,
                       c.page_number,
                       c.chunk_index,
                       1 - (c.embedding <=> %s::vector) AS score
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s;
                """,
                (_vec_literal(query_vector), _vec_literal(query_vector), top_k),
            )
            return cur.fetchall()

    # ---- read path: keyword search (built-in full-text; BM25 later) ----------
    def search_by_keyword(
        self, query_text: str, top_k: int
    ) -> list[tuple[str, str, int, int, float]]:
        """Return the top_k chunks by KEYWORD relevance, using Postgres built-in
        full-text search (tsvector + ts_rank_cd).

        WHY built-in and not BM25: true BM25 needs an extension (pg_textsearch /
        ParadeDB) not present in the base pgvector image. Built-in FTS works in ANY
        Postgres with zero setup, so the hybrid strategy is runnable today. BM25 is
        a drop-in upgrade behind this same method IF an eval proves it's worth it
        (cheap-and-broad first). ts_rank_cd considers term proximity/density.

        'simple' config = language-agnostic tokenizer: works for BOTH Arabic and
        English (no stemming, but exact-term matching — which is the whole point of
        the keyword leg: catch literal terms like 'JWT' or 'البند').

        🔴 WHY NOT websearch_to_tsquery: it ANDs every word together, so a full
        question ("What command removes a local image?") only matches a chunk that
        contains ALL of those words at once — which, with no stemming, is almost
        never true. Measured: it returned 0 rows for every golden question, making
        hybrid silently collapse to pure dense. We OR the terms instead, so ANY
        term can match and ts_rank_cd rewards chunks that hit MORE of them (and hit
        them densely) — the behaviour a keyword leg is supposed to have.
        """
        # Meaningful lexemes only (stopwords + 1-char tokens dropped), OR-ed so ANY
        # term can match and ts_rank_cd rewards chunks hitting MORE of them densely.
        terms = _keyword_terms(query_text)
        if not terms:
            return []
        ts_or = " | ".join(terms)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.text,
                       d.source_filename,
                       c.page_number,
                       c.chunk_index,
                       ts_rank_cd(
                           to_tsvector('simple', c.text),
                           to_tsquery('simple', %s)
                       ) AS score
                FROM chunks c
                JOIN documents d ON d.id = c.document_id
                WHERE to_tsvector('simple', c.text)
                      @@ to_tsquery('simple', %s)
                ORDER BY score DESC
                LIMIT %s;
                """,
                (ts_or, ts_or, top_k),
            )
            return cur.fetchall()