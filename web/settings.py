"""
web/settings.py — Django settings for the RAG Lab control panel.

Deliberately MINIMAL. This Django project does exactly one job: serve the
control-panel UI + the /api/ask endpoint. All data access goes through our own
raw-psycopg repository against pgvector — we do NOT use Django's ORM. So:

  * DATABASES is empty (no ORM, no migrations, nothing to migrate).
  * auth / sessions / admin / contenttypes are NOT installed (they'd need the ORM).

That keeps the surface tiny and honest: Django is just the web edge; the RAG
engine underneath is framework-agnostic (the whole point of the layered design,
so the planned FastAPI migration touches only this thin edge).
"""

from __future__ import annotations

import os
from pathlib import Path

# repo root (this file is web/settings.py -> parent.parent = root)
BASE_DIR = Path(__file__).resolve().parent.parent

# --- security: dev defaults, overridable by env for any real deployment --------
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "dev-insecure-key-change-me-in-production"
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")

# --- apps: only what a template-rendering, ORM-free UI needs --------------------
INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "web.ragapp",
]

# --- middleware: minimal. No sessions/auth/messages (no ORM to back them). ------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

ROOT_URLCONF = "web.urls"
WSGI_APPLICATION = "web.wsgi.application"

# --- templates: APP_DIRS finds web/ragapp/templates/index.html automatically ----
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

# --- database: NONE. We use raw psycopg + pgvector via core/repository.py. -------
DATABASES: dict = {}

# --- static files (the UI is self-contained, but keep the plumbing sane) --------
STATIC_URL = "static/"

# --- i18n / tz ------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
