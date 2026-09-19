"""Ensure the Celery app is created when Django starts.

Importing `celery_app` here means `@shared_task` decorators resolve to our
configured app even in the `web` process (the producer), not just the worker.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
