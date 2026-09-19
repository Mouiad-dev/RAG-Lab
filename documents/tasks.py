"""Celery tasks for the documents domain.

A task is a THIN wrapper over the pipeline — zero business logic here (the same
"a tool/task is a thin adapter over a service" rule we'll reuse for tool calling).
This is the only new thing Step 2.2 adds around 2.1's proven `ingest_document`:
it lets the work run in a separate worker process instead of inline.
"""

from __future__ import annotations

from celery import shared_task

from .pipeline import ingest_document


@shared_task(name="documents.ingest_document")
def ingest_document_task(document_id: int) -> dict:
    """Run the ingestion pipeline for one document in the background.

    Returns a small summary for the Celery result backend / logs; the durable
    status lives on the `Job` row, which the pipeline advances as it runs.
    """
    job = ingest_document(document_id)
    return {"job_id": job.id, "state": job.state}
