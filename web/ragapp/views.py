"""
web/ragapp/views.py  —  thin views. Orchestrate only; logic lives in services.py.
"""

from __future__ import annotations

import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from web.ragapp import services


def index(request):
    """Render the control panel + chat UI, seeded with the base config defaults."""
    base = services.load_base_config()
    r = base.get("retrieval", {})
    ctx = {
        "default_mode": r.get("mode", "naive"),
        "default_top_k": r.get("top_k", 5),
        "default_qt": r.get("query_transform", "none"),
        "modes": ["naive", "hybrid", "query_transform", "crag", "graph", "agentic"],
        "qt_modes": ["none", "rewrite", "hyde"],
        "llm_model": base.get("llm", {}).get("model", "?"),
        "embed_model": base.get("embeddings", {}).get("provider_model", "?"),
    }
    return render(request, "index.html", ctx)


@csrf_exempt  # dev-only convenience; add CSRF token handling for production
@require_http_methods(["POST"])
def ask(request):
    """Answer one question with the config overrides from the UI."""
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid JSON body"}, status=400)

    question = (payload.get("question") or "").strip()
    if not question:
        return JsonResponse({"error": "question is required"}, status=400)

    overrides = {
        "mode": payload.get("mode", "naive"),
        "top_k": payload.get("top_k", 5),
        "query_transform": payload.get("query_transform", "none"),
        "rerank_enabled": payload.get("rerank_enabled", False),
        "graph_enabled": payload.get("mode") == "graph",
        "agentic_enabled": payload.get("mode") == "agentic",
    }
    try:
        result = services.answer_question(question, overrides)
    except Exception as e:  # surface engine errors cleanly to the UI
        return JsonResponse({"error": f"{type(e).__name__}: {e}"}, status=500)
    return JsonResponse(result)