"""Run the ingestion pipeline for one existing Document, synchronously.

Step 2.1's driver: this stands in for the async trigger that Celery will provide in
2.2. It just calls the pipeline and prints the resulting Job so we can watch a real
file go extract -> chunk -> embed -> store from the command line.

    docker compose exec web python manage.py ingest_document <document_id>
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from documents.models import Document
from documents.pipeline import ingest_document
from documents.repositories import ChunkRepository


class Command(BaseCommand):
    help = "Synchronously ingest one Document (extract -> chunk -> embed -> store)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("document_id", type=int, help="ID of the Document to ingest")

    def handle(self, *args, **options) -> None:
        document_id = options["document_id"]
        try:
            job = ingest_document(document_id)
        except Document.DoesNotExist:
            raise CommandError(f"No Document with id={document_id}")
        except Exception as exc:  # pipeline already marked the Job failed
            raise CommandError(f"Ingestion failed: {exc}")

        chunk_count = ChunkRepository().list_for_document(document_id).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Job#{job.id} -> {job.state} | doc={document_id} | chunks={chunk_count}"
            )
        )
