"""The eval golden set.

A GoldenQuestion is an exam question with a KNOWN correct answer and known source.
Running the system over these turns "is it good?" into real numbers (recall@k,
faithfulness). Browser-editable UI comes in Phase 5; the model exists now so the
eval harness has something to read.
"""

from django.db import models


class GoldenQuestion(models.Model):
    question = models.TextField()
    expected_answer = models.TextField(blank=True)

    # Where the answer lives — used to score RETRIEVAL recall separately from the
    # answer. Kept as loose strings for now (no hard FK to Document) so the golden
    # set can be authored independently of what's currently ingested.
    expected_source = models.CharField(max_length=500, blank=True)  # doc name/id
    expected_page = models.PositiveIntegerField(null=True, blank=True)

    language = models.CharField(max_length=20, blank=True)  # ar / en
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.question[:60]
