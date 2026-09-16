"""Repositories: the ONLY place ORM queries for the documents domain live.

Why (the "one counter clerk"): services and views never touch `Document.objects`
directly. They ask a repository. When *how* we query changes (add a filter, add
caching, or — for chunks — swap in raw pgvector search), only the repository
changes; callers stay the same. It also lets tests swap a fake repository to check
their own logic without a real DB.
"""

from __future__ import annotations

from django.db.models import QuerySet

from .models import Document


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
