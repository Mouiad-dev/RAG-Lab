"""Show the advisor's chunker recommendation for one Document (no ingestion).

    docker compose exec web python manage.py advise_document <id>
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from documents.advisor import advise
from documents.models import Document
from documents.repositories import DocumentRepository


class Command(BaseCommand):
    help = "Profile a Document and recommend a chunking strategy (with a reason)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("document_id", type=int)

    def handle(self, *args, **options) -> None:
        try:
            document = DocumentRepository().get(options["document_id"])
        except Document.DoesNotExist:
            raise CommandError(f"No Document with id={options['document_id']}")

        rec = advise(document)
        self.stdout.write(self.style.SUCCESS(f"Recommended chunker: {rec.strategy}"))
        self.stdout.write(f"Reason: {rec.reason}")
        self.stdout.write(f"Profile: {rec.profile.model_dump()}")
