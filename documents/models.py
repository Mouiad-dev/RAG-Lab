"""The RAG domain models.

`Document` = the record (the "library index card") for one uploaded file. The
actual bytes live on disk via `file` (a FileField); the DB stores only the path
plus structured facts about the file.

Design note (fat model): behavior that belongs to a single document lives here as
methods (e.g. `mark_ready`). Talking to the DB about *many* documents lives in the
DocumentRepository, not here.
"""

from django.db import models
from pgvector.django import VectorField

# Embedding dimension of our dev embedder (BGE-M3 = 1024). Every chunk vector AND
# every query vector must share this. Changing embedders => change this + re-embed
# everything (a migration). Kept as one constant so there's a single source of truth.
EMBEDDING_DIM = 1024


class Collection(models.TextChoices):
    """Which space a document belongs to. Keeps the ask-space and the eval-space
    isolated so they can never contaminate each other (PRODUCT.md)."""

    NOTEBOOK = "notebook", "Notebook (ask)"
    GOLDEN = "golden", "Golden-set (eval only)"


class DocumentStatus(models.TextChoices):
    """Coarse ingestion status. The per-file `Job` model (Step 1.4) tracks the
    fine-grained stages; this is the document's own summary state."""

    UPLOADED = "uploaded", "Uploaded"
    PROCESSING = "processing", "Processing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class Document(models.Model):
    title = models.CharField(max_length=500)
    original_filename = models.CharField(max_length=500)
    file = models.FileField(upload_to="documents/")

    collection = models.CharField(
        max_length=20,
        choices=Collection.choices,
        default=Collection.NOTEBOOK,
        db_index=True,
    )
    content_type = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=20, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=DocumentStatus.choices,
        default=DocumentStatus.UPLOADED,
        db_index=True,
    )
    error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["collection", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.collection}/{self.status})"

    def mark_processing(self) -> None:
        self.status = DocumentStatus.PROCESSING
        self.error = ""
        self.save(update_fields=["status", "error", "updated_at"])

    def mark_ready(self) -> None:
        self.status = DocumentStatus.READY
        self.error = ""
        self.save(update_fields=["status", "error", "updated_at"])

    def mark_failed(self, reason: str) -> None:
        self.status = DocumentStatus.FAILED
        self.error = reason
        self.save(update_fields=["status", "error", "updated_at"])


class Chunk(models.Model):
    """One small slice of a document's text + its embedding vector.

    Retrieval searches Chunks (not whole Documents): find the few chunks nearest
    to the question, show only those to the LLM. `page` becomes the citation.
    """

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,   # delete a doc -> its chunks go too
        related_name="chunks",
    )

    text = models.TextField()               # what the LLM actually reads
    ordinal = models.PositiveIntegerField()  # position within the document (0,1,2,...)
    page = models.PositiveIntegerField(null=True, blank=True)  # source page (citation)
    token_count = models.PositiveIntegerField(null=True, blank=True)  # context budgeting

    # The embedding. null until the chunk is embedded (chunks are created first,
    # embedded second). See EMBEDDING_DIM for the fixed dimension rule.
    vector = VectorField(dimensions=EMBEDDING_DIM, null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)  # heading/section/etc.

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id", "ordinal"]
        constraints = [
            # a document can't have two chunks at the same position
            models.UniqueConstraint(
                fields=["document", "ordinal"], name="uniq_chunk_doc_ordinal"
            ),
        ]
        # NOTE(scale): add an ANN index (HNSW/IVFFlat) on `vector` in a later step,
        # once we have enough chunks that exact search is too slow to justify it.
        # Measure first (the one rule) before adding the index.

    def __str__(self) -> str:
        return f"Chunk#{self.ordinal} of doc {self.document_id}"

    @property
    def is_embedded(self) -> bool:
        return self.vector is not None
