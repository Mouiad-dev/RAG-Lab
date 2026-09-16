"""The RAG domain models.

`Document` = the record (the "library index card") for one uploaded file. The
actual bytes live on disk via `file` (a FileField); the DB stores only the path
plus structured facts about the file.

Design note (fat model): behavior that belongs to a single document lives here as
methods (e.g. `mark_ready`). Talking to the DB about *many* documents lives in the
DocumentRepository, not here.
"""

from django.db import models


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
