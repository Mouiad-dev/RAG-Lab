"""Repository for the golden set — the only place GoldenQuestion.objects is used."""

from __future__ import annotations

from django.db.models import QuerySet

from .models import GoldenQuestion


class GoldenQuestionRepository:
    def create(
        self,
        *,
        question: str,
        expected_answer: str = "",
        expected_source: str = "",
        expected_page: int | None = None,
        language: str = "",
        notes: str = "",
    ) -> GoldenQuestion:
        return GoldenQuestion.objects.create(
            question=question,
            expected_answer=expected_answer,
            expected_source=expected_source,
            expected_page=expected_page,
            language=language,
            notes=notes,
        )

    def all(self) -> QuerySet[GoldenQuestion]:
        return GoldenQuestion.objects.all()
