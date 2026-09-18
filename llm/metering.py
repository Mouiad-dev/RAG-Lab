"""MeteredLLMClient — a Decorator that wraps ANY LLMClient and logs the receipt.

Pattern: Decorator. It has the same interface as what it wraps (so it's itself an
LLMClient), adds a behavior (cost logging), and delegates the real work. Because
logging lives here — not in each adapter — every backend is metered identically:
"log usage/cost on EVERY call" (§5b) is enforced in one place.
"""

from __future__ import annotations

from .ports import LLMClient, LLMResponse
from .pricing import compute_cost


class MeteredLLMClient:
    def __init__(self, inner: LLMClient, repo=None):
        self._inner = inner
        self.provider = inner.provider
        self.model = inner.model
        # Imported lazily so the llm/ package doesn't require Django at import time.
        if repo is None:
            from core.repositories import LLMCallRepository

            repo = LLMCallRepository()
        self._repo = repo

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
        resp = self._inner.complete(
            prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            purpose=purpose,
            prompt_ref=prompt_ref,
        )

        cost = compute_cost(
            self.provider,
            self.model,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cache_creation_tokens=resp.cache_creation_tokens,
            cache_read_tokens=resp.cache_read_tokens,
        )

        self._repo.log(
            provider=self.provider,
            model=self.model,
            purpose=purpose,
            prompt_ref=prompt_ref,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cache_creation_tokens=resp.cache_creation_tokens,
            cache_read_tokens=resp.cache_read_tokens,
            input_cost=cost.input_cost,
            output_cost=cost.output_cost,
            cache_write_cost=cost.cache_write_cost,
            cache_read_cost=cost.cache_read_cost,
            currency=cost.currency,
            price_ref=cost.price_ref,
            latency_ms=resp.latency_ms,
        )
        return resp
