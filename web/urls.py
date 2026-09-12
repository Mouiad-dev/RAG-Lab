"""
web/urls.py — the URL map (which address calls which view).

  GET  /          -> index : render the control panel + chat UI
  POST /api/ask   -> ask   : answer one question with the UI's live config overrides
                             (matches the fetch("/api/ask") call in index.html)
"""

from __future__ import annotations

from django.urls import path

from web.ragapp import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/ask", views.ask, name="ask"),
]
