"""Trigger ingestion for one existing Document.

Step 2.2 makes this a **producer**: by default it creates the `Job` row (state
`queued`) and hands the work to Celery via `.delay()`, returning IMMEDIATELY — the
slow pipeline runs in the separate `worker` container. This is the same shape the
future upload view will use (create Job, enqueue, return the id to the browser).

    docker compose exec web python manage.py ingest_document <id>          # async (default)
    docker compose exec web python manage.py ingest_document <id> --sync   # inline (debug)

The worker reuses the queued Job (pipeline: latest-for-document), so status is
queryable the instant this command returns.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from documents.models import Document
from documents.pipeline import ingest_document
from documents.repositories import ChunkRepository, DocumentRepository, JobRepository
from documents.tasks import ingest_document_task


class Command(BaseCommand):
    help = "Ingest one Document (async by default; --sync runs inline)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("document_id", type=int, help="ID of the Document to ingest")
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run the pipeline inline and block, instead of enqueuing to Celery.",
        )

    def handle(self, *args, **options) -> None:
        document_id = options["document_id"]

        if options["sync"]:
            try:
                job = ingest_document(document_id)
            except Document.DoesNotExist:
                raise CommandError(f"No Document with id={document_id}")
            except Exception as exc:  # pipeline already marked the Job failed
                raise CommandError(f"Ingestion failed: {exc}")
            chunk_count = ChunkRepository().list_for_document(document_id).count()
            self.stdout.write(
                self.style.SUCCESS(
                    f"[sync] Job#{job.id} -> {job.state} | doc={document_id} | "
                    f"chunks={chunk_count}"
                )
            )
            return

        # Async (default): create the queued Job now so status is visible instantly,
        # then hand the work to a worker and return without blocking.
        try:
            document = DocumentRepository().get(document_id)
        except Document.DoesNotExist:
            raise CommandError(f"No Document with id={document_id}")

        job = JobRepository().create(document=document)
        result = ingest_document_task.delay(document_id)
        self.stdout.write(
            self.style.SUCCESS(
                f"[queued] Job#{job.id} (state={job.state}) | task={result.id} | "
                f"doc={document_id} — the worker will process it."
            )
        )
