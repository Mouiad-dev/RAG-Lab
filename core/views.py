"""Cross-cutting views. Right now: a liveness/readiness health check.

Pattern note (thin view): the view only *orchestrates* — it calls small check
helpers and serializes the result. It holds no business logic itself. This is a
deliberately minimal preview of the Controller -> Service layering used later.
"""

import os
import urllib.request

from django.db import connection
from django.http import JsonResponse


def _check_database() -> tuple[bool, str]:
    """Can we reach Postgres right now? Trivial round-trip: SELECT 1."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return True, "ok"
    except Exception as exc:  # surface the reason, don't crash the endpoint
        return False, f"error: {exc}"


def _check_ollama() -> tuple[bool, str]:
    """Is the Ollama server reachable? Ask for its version."""
    base_url = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
    try:
        with urllib.request.urlopen(f"{base_url}/api/version", timeout=5) as resp:
            if resp.status == 200:
                return True, "ok"
            return False, f"http {resp.status}"
    except Exception as exc:
        return False, f"error: {exc}"


def health(request):
    """GET /health/ — returns per-dependency status.

    HTTP 200 only if every dependency is reachable; 503 otherwise, so that
    monitoring tools (Docker, CI, load balancers) can act on the status code.
    """
    db_ok, db_detail = _check_database()
    ollama_ok, ollama_detail = _check_ollama()

    all_ok = db_ok and ollama_ok
    payload = {
        "status": "ok" if all_ok else "unhealthy",
        "checks": {
            "database": db_detail,
            "ollama": ollama_detail,
        },
    }
    return JsonResponse(payload, status=200 if all_ok else 503)
