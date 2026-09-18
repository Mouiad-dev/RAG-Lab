"""Ollama adapter — a real HTTP call to a local model ($0, no vendor lock-in).

Maps Ollama's response into OUR LLMResponse. No Ollama-specific dict escapes this
file. Reads the base URL from OLLAMA_BASE_URL so the same code works on host and in
docker-compose.
"""

from __future__ import annotations

import os
import time

import httpx

from ..ports import LLMResponse
from ..registry import register_provider


# TODO: later to change this be controlled by admin
DEFAULT_MODEL = "qwen2.5:0.5b"


@register_provider("ollama")
class OllamaClient:
    """An LLMClient backed by a local Ollama server."""

    provider = "ollama"

    def __init__(self, model: str | None = None, *, base_url: str | None = None, timeout: float = 60.0):
        self.model = model or DEFAULT_MODEL
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")).rstrip("/")
        self.timeout = timeout

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.0,
        max_tokens: int = 1024,
        purpose: str = "",
        prompt_ref: str = "",
    ) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,  # one JSON object back (no streaming for now)
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }

        started = time.perf_counter()
        resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        latency_ms = int((time.perf_counter() - started) * 1000)
        data = resp.json()

        return LLMResponse(
            text=data["message"]["content"],
            model=self.model,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            # Ollama reports done_reason like "stop" / "length".
            stop_reason=data.get("done_reason"),
            latency_ms=latency_ms,
        )
