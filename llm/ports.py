"""The LLM boundary (Port).

`LLMResponse` is OUR type — the only shape LLM results take once they cross the
adapter boundary. No vendor type (anthropic.types.*, ollama dicts) ever escapes an
adapter; it is mapped into an LLMResponse first. That keeps services/views/models
provider-agnostic.

`LLMClient` is a typing.Protocol (structural interface): any object with a matching
`complete()` method — and `provider`/`model` attributes — IS an LLMClient, no
inheritance required. Ollama, Anthropic, and the test Fake all satisfy it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class LLMResponse(BaseModel):
    """The validated result of one LLM call — our own type, not a vendor's."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0  # tokens written to the prompt cache
    cache_read_tokens: int = 0      # tokens served from the prompt cache (a hit)
    stop_reason: str | None = None  # why generation stopped (end_turn / max_tokens / ...)
    latency_ms: int | None = None


@runtime_checkable
class LLMClient(Protocol):
    """Structural interface every LLM adapter satisfies."""

    provider: str
    model: str

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
        """Send a prompt, return a validated LLMResponse.

        `purpose`/`prompt_ref` are call metadata used for the cost receipt
        (they don't change the generation). Default `temperature=0.0` — anything
        parsed downstream must be deterministic.
        """
        ...
