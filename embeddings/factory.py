"""Factory — reads config, looks up the embedder in the registry. No if/else."""

from __future__ import annotations

import os

from .ports import Embedder
from .registry import get_embedder_builder


def build_embedder(*, provider: str | None = None, model: str | None = None) -> Embedder:
    provider = provider or os.environ.get("EMBEDDING_PROVIDER", "ollama")
    # Provider-specific override (e.g. OLLAMA_EMBEDDING_MODEL). Unset -> adapter default.
    model = model or os.environ.get(f"{provider.upper()}_EMBEDDING_MODEL")

    builder = get_embedder_builder(provider)  # polymorphic lookup
    return builder(model)
