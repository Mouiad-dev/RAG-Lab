"""Repositories: the ONLY place ORM queries for the documents domain live.

Why (the "one counter clerk"): services and views never touch `Document.objects`
directly. They ask a repository. When *how* we query changes (add a filter, add
caching, or — for chunks — swap in raw pgvector search), only the repository
changes; callers stay the same. It also lets tests swap a fake repository to check
their own logic without a real DB.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.db.models import QuerySet
from pgvector.django import CosineDistance

from .models import Chunk, Document, Job


class DocumentRepository:
    """All read/write access to Document rows. (Reads + writes kept together for
    now; we split into a separate Selector only if it earns its place — KISS.)"""

    def create(
        self,
        *,
        title: str,
        original_filename: str,
        file,
        collection: str,
        content_type: str = "",
        language: str = "",
        size_bytes: int | None = None,
        page_count: int | None = None,
    ) -> Document:
        return Document.objects.create(
            title=title,
            original_filename=original_filename,
            file=file,
            collection=collection,
            content_type=content_type,
            language=language,
            size_bytes=size_bytes,
            page_count=page_count,
        )

    def get(self, doc_id: int) -> Document:
        """Fetch one document by id; raises Document.DoesNotExist if missing."""
        return Document.objects.get(pk=doc_id)

    def list_in_collection(self, collection: str) -> QuerySet[Document]:
        """All documents in a given collection (newest first via Meta.ordering)."""
        return Document.objects.filter(collection=collection)


class ChunkRepository:
    """All read/write access to Chunk rows — including the ONE place vector search
    lives (the plan's quarantined pgvector fragment)."""

    def bulk_create(self, chunks: Sequence[Chunk]) -> list[Chunk]:
        """Save many chunks in one round-trip (ingestion writes in batches)."""
        return Chunk.objects.bulk_create(list(chunks))

    def list_for_document(self, document_id: int) -> QuerySet[Chunk]:
        return Chunk.objects.filter(document_id=document_id)

    def search_by_vector(
        self,
        query_vector: Sequence[float],
        collection: str,
        top_k: int = 5,
    ) -> list[Chunk]:
        """🔴 The quarantined vector search — the only place similarity search lives.

        pgvector's cosine-distance operator (`<=>`) has no plain ORM syntax, so we
        express it via pgvector's `CosineDistance` helper as an annotation. This keeps
        it ORM-native and parameterized (no raw string / injection risk). Everywhere
        else in the app stays pure ORM; if search ever changes, only this method does.

        Returns Chunks ordered nearest-first, each carrying a `.distance` attribute
        (smaller = more similar). We metadata-PRE-filter by collection first (never
        post-filter) — precision + Notebook/Golden isolation.
        """
        return list(
            Chunk.objects.filter(
                document__collection=collection,
                vector__isnull=False,
            )
            .annotate(distance=CosineDistance("vector", query_vector))
            .order_by("distance")[:top_k]
        )


class JobRepository:
    """Read/write access to ingestion Job rows."""

    def create(self, *, document: Document) -> Job:
        return Job.objects.create(document=document)

    def get(self, job_id: int) -> Job:
        return Job.objects.get(pk=job_id)

    def latest_for_document(self, document_id: int) -> Job | None:
        return Job.objects.filter(document_id=document_id).order_by("-created_at").first()
