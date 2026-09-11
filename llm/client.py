"""
llm/client.py  —  the LLM Port + Adapter.

Same pattern as the embeddings layer: a thin Port (interface) with one Adapter per
provider. Callers depend on the Port, never a concrete provider, so we can swap
Ollama (free, dev) <-> Claude (paid, final demo) by changing config, not code.

LOCKED decision: all development runs on Ollama at $0; only the final demo flips
provider to claude (which needs a separate paid API key — Claude Pro is a chat
subscription, NOT API credits).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    model: str
    # token counts when the provider reports them — feeds the cost eval later.
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class LLMClient(ABC):
    """Port: the contract every LLM provider must satisfy."""

    @abstractmethod
    def complete(self, system: str, user: str, temperature: float = 0.0) -> LLMResponse:
        """Given a system instruction and a user message, return the model's reply.

        temperature=0.0 by default: grounded Q&A must be deterministic, not creative.
        """
        raise NotImplementedError


class OllamaLLM(LLMClient):
    """Adapter: a local chat model served by the ollama box ($0)."""

    def __init__(
        self,
        model: str = "llama3.1:8b",
        base_url: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
        self.timeout = timeout

    def complete(self, system: str, user: str, temperature: float = 0.0) -> LLMResponse:
        import httpx
        resp = httpx.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return LLMResponse(
            text=data["message"]["content"],
            model=self.model,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
        )


class ClaudeLLM(LLMClient):
    """Adapter: Anthropic Claude, for the final demo only (paid API key required)."""

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")

    def complete(self, system: str, user: str, temperature: float = 0.0) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError(
                "ClaudeLLM needs ANTHROPIC_API_KEY (a paid API key, NOT Claude Pro). "
                "Keep provider=ollama for dev; only set this for the final demo."
            )
        import httpx
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 1024,
                "temperature": temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        return LLMResponse(
            text="".join(b.get("text", "") for b in data.get("content", [])),
            model=self.model,
            prompt_tokens=usage.get("input_tokens"),
            completion_tokens=usage.get("output_tokens"),
        )


def build_llm(cfg: dict) -> LLMClient:
    """Construct the LLM the config asks for (llm.provider)."""
    llm = cfg.get("llm", {})
    provider = llm.get("provider", "ollama")
    if provider == "ollama":
        return OllamaLLM(model=llm.get("model", "llama3.1:8b"))
    if provider == "claude":
        return ClaudeLLM(model=llm.get("model", "claude-sonnet-4-6"))
    raise ValueError(f"unknown llm.provider: {provider!r}")