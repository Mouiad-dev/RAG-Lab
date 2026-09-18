"""Factory — reads config, looks up the provider in the registry, wraps in metering.

No if/else: the provider is selected polymorphically via the registry. Every client
comes back wrapped in MeteredLLMClient, so every call is logged.
"""

from __future__ import annotations

import os

from .metering import MeteredLLMClient
from .ports import LLMClient
from .registry import get_provider_builder


def build_llm_client(*, provider: str | None = None, model: str | None = None) -> LLMClient:
    provider = provider or os.environ.get("LLM_PROVIDER", "ollama")
    # Provider-specific model override (e.g. OLLAMA_MODEL / ANTHROPIC_MODEL). Computed
    # key, not a branch. If unset, model stays None and the adapter's DEFAULT_MODEL wins.
    model = model or os.environ.get(f"{provider.upper()}_MODEL")

    # Polymorphic lookup — no branching. The registry self-loads adapters.
    builder = get_provider_builder(provider)
    return MeteredLLMClient(builder(model))
