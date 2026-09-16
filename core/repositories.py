"""Repository for observability — the only place LLMCall/CallCost .objects are used.

`log()` writes the usage row AND its cost breakdown together (one transaction); the
LLM adapters (Step 1.5) call it after each request. `total_cost()` is the aggregate
the budget dashboard reads.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from .models import CallCost, LLMCall


class LLMCallRepository:
    @transaction.atomic
    def log(
        self,
        *,
        provider: str,
        model: str,
        purpose: str = "",
        prompt_ref: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
        # cost breakdown (computed by the caller via the price book, 1.5)
        input_cost: Decimal | float = 0,
        output_cost: Decimal | float = 0,
        cache_write_cost: Decimal | float = 0,
        cache_read_cost: Decimal | float = 0,
        currency: str = "USD",
        price_ref: str = "",
        latency_ms: int | None = None,
    ) -> LLMCall:
        call = LLMCall.objects.create(
            provider=provider,
            model=model,
            purpose=purpose,
            prompt_ref=prompt_ref,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation_tokens,
            cache_read_tokens=cache_read_tokens,
            latency_ms=latency_ms,
        )
        total = (
            Decimal(str(input_cost))
            + Decimal(str(output_cost))
            + Decimal(str(cache_write_cost))
            + Decimal(str(cache_read_cost))
        )
        CallCost.objects.create(
            llm_call=call,
            input_cost=input_cost,
            output_cost=output_cost,
            cache_write_cost=cache_write_cost,
            cache_read_cost=cache_read_cost,
            total_cost=total,
            currency=currency,
            price_ref=price_ref,
        )
        return call

    def total_cost(self) -> Decimal:
        return CallCost.objects.aggregate(t=Sum("total_cost"))["t"] or Decimal("0")
