#!/usr/bin/env python
"""manage.py — Django's command-line entry point (runserver, check, ...).

Run from the repo root so that the top-level packages (web, core, retrieval,
ingestion, ...) are all importable, exactly as the app's imports expect
(e.g. `from web.ragapp import services`, `from core.repository import ...`).
"""

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "Couldn't import Django. Is it installed and is your virtualenv active? "
            "Run: pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
