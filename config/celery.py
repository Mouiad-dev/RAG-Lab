"""The Celery application — the entry point the worker process runs.

`celery -A config worker` imports THIS module to find `app`. It reads all its
settings from Django's settings (the `CELERY_` prefix) so there's one config
source, and `autodiscover_tasks()` imports every app's `tasks.py` so a
`@shared_task` is registered just by living in `documents/tasks.py`.
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("rag_lab")

# Pull CELERY_* keys from Django settings (namespace keeps them grouped/obvious).
app.config_from_object("django.conf:settings", namespace="CELERY")

# Find tasks.py in each INSTALLED_APPS app (e.g. documents/tasks.py).
app.autodiscover_tasks()
