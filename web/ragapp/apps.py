"""web/ragapp/apps.py — the Django app definition for the control panel."""

from __future__ import annotations

from django.apps import AppConfig


class RagAppConfig(AppConfig):
    # dotted path because the app lives at web/ragapp, not top-level ragapp.
    name = "web.ragapp"
    label = "ragapp"
