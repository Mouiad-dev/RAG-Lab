"""The ingestion pipeline — the assembly line that turns a stored file into
searchable, embedded Chunk rows.

    extract  ->  chunk  ->  embed  ->  store

Step 2.1 runs this SYNCHRONOUSLY (in-process, blocking) so we can prove every stage
connects on a small file before adding a background worker. Step 2.2 will move THIS
SAME function behind Celery + Redis; the pipeline body won't change — only who calls
it and from where.

Design:
- Pipeline pattern: discrete stages in order, with the `Job` state machine advanced
  between them (mark_extracting -> mark_chunking -> mark_embedding -> ready/failed) so
  the UI can show live progress (meaningfully so once async in 2.2).
- Ports/Strategy: it depends on the `Chunker` and `Embedder` interfaces via factories,
  never on a concrete adapter — flip `CHUNKER` / `EMBEDDING_PROVIDER` in config to swap.
- Repositories: all DB access goes through the repos; the pipeline holds orchestration
  only. The store step is atomic (clear old chunks + insert new) so a re-ingest is
  idempotent and a mid-store crash can't leave half a document.
"""

from __future__ import annotations

from django.db import transaction

from chunkers.factory import build_chunker
from chunkers.ports import Chunker
from embeddings.factory import build_embedder
from embeddings.ports import Embedder

from .extractors import extract_text
from .models import Chunk, Job
from .repositories import ChunkRepository, DocumentRepository, JobRepository


class EmptyDocumentError(Exception):
    """The file produced no chunkable text (empty or whitespace-only)."""


def ingest_document(
    document_id: int,
    *,
    chunker: Chunker | None = None,
    embedder: Embedder | None = None,
) -> Job:
    """Run the full pipeline for one document. Returns the finished Job.

    `chunker`/`embedder` are injectable for tests; in normal use they're built from
    config by the factories. On any failure the Document and Job are marked failed
    (with the reason) and the exception re-raised for the caller/worker to see.
    """
    documents = DocumentRepository()
    chunks = ChunkRepository()
    jobs = JobRepository()

    document = documents.get(document_id)
    # Reuse the latest Job if one exists (a re-ingest), else open a fresh one.
    job = jobs.latest_for_document(document_id) or jobs.create(document=document)

    try:
        document.mark_processing()

        # 1) extract -------------------------------------------------------
        job.mark_extracting()
        text = extract_text(document)

        # 2) chunk ---------------------------------------------------------
        job.mark_chunking()
        chunker = chunker or build_chunker()
        pieces = chunker.chunk(text)
        if not pieces:
            raise EmptyDocumentError("no chunkable text produced from the document")

        # 3) embed ---------------------------------------------------------
        job.mark_embedding()
        embedder = embedder or build_embedder()
        vectors = embedder.embed([p.text for p in pieces])
        if len(vectors) != len(pieces):
            raise RuntimeError(
                f"embedder returned {len(vectors)} vectors for {len(pieces)} chunks"
            )

        # 4) store (atomic: clear old + insert new) ------------------------
        rows = [
            Chunk(
                document=document,
                text=p.text,
                ordinal=p.ordinal,
                page=p.page,
                token_count=p.token_count,
                metadata=p.metadata,
                vector=vector,
            )
            for p, vector in zip(pieces, vectors)
        ]
        with transaction.atomic():
            chunks.delete_for_document(document_id)  # idempotent re-ingest
            chunks.bulk_create(rows)

        document.mark_ready()
        job.mark_ready()
        return job

    except Exception as exc:  # noqa: BLE001 — record the failure, then re-raise
        reason = f"{type(exc).__name__}: {exc}"
        document.mark_failed(reason)
        job.mark_failed(reason)
        raise
