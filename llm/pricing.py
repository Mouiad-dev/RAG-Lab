"""The price book (Pydantic, in code — NOT a DB table).

Prices are static reference data that change rarely and live with the code: git
history IS the price history, and no migration is needed to read them. We snapshot
the computed dollars + `price_ref` onto CallCost, so historical costs stay accurate
even when these numbers change.

`ModelPrice` IS the "price model" — a typed, validated object. Promote it to a DB
table only if runtime-editable prices are ever needed (leave that door open).

Pricing snapshot: 2026-06-24 (Anthropic first-party rates). Re-check monthly.
Cache accounting: cache-write ≈ 1.25× input, cache-read ≈ 0.1× input.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

# Bump this string when any price changes; it gets stamped onto each CallCost.
PRICE_REF = "2026-06-24"

_MTOK = Decimal(1_000_000)  # prices are quoted per million tokens


class ModelPrice(BaseModel):
    """Per-million-token rates for one provider/model. Decimal — it's money."""

    input_per_mtok: Decimal
    output_per_mtok: Decimal
    cache_write_per_mtok: Decimal = Decimal("0")
    cache_read_per_mtok: Decimal = Decimal("0")
    currency: str = "USD"


class CostBreakdown(BaseModel):
    """The computed cost of one call — mirrors the CallCost DB row's money fields."""

    input_cost: Decimal
    output_cost: Decimal
    cache_write_cost: Decimal
    cache_read_cost: Decimal
    total_cost: Decimal
    currency: str = "USD"
    price_ref: str = PRICE_REF


# Keyed "provider/model". Ollama models are free -> handled in compute_cost().
PRICE_BOOK: dict[str, ModelPrice] = {
    "anthropic/claude-opus-5": ModelPrice(
        input_per_mtok=Decimal("5"), output_per_mtok=Decimal("25"),
        cache_write_per_mtok=Decimal("6.25"), cache_read_per_mtok=Decimal("0.50"),
    ),
    "anthropic/claude-sonnet-5": ModelPrice(
        input_per_mtok=Decimal("2"), output_per_mtok=Decimal("10"),
        cache_write_per_mtok=Decimal("2.50"), cache_read_per_mtok=Decimal("0.20"),
    ),
    "anthropic/claude-haiku-4-5": ModelPrice(
        input_per_mtok=Decimal("1"), output_per_mtok=Decimal("5"),
        cache_write_per_mtok=Decimal("1.25"), cache_read_per_mtok=Decimal("0.10"),
    ),
}

# Free local models: any Ollama model costs $0 (we still record a zero breakdown).
_FREE = ModelPrice(input_per_mtok=Decimal("0"), output_per_mtok=Decimal("0"))


def _lookup(provider: str, model: str) -> ModelPrice:
    if provider == "ollama":
        return _FREE
    return PRICE_BOOK.get(f"{provider}/{model}", _FREE)


def compute_cost(
    provider: str,
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> CostBreakdown:
    """Turn token usage into a money breakdown via the price book."""
    p = _lookup(provider, model)

    def cost(tokens: int, rate: Decimal) -> Decimal:
        return (Decimal(tokens) / _MTOK) * rate

    input_cost = cost(input_tokens, p.input_per_mtok)
    output_cost = cost(output_tokens, p.output_per_mtok)
    cache_write_cost = cost(cache_creation_tokens, p.cache_write_per_mtok)
    cache_read_cost = cost(cache_read_tokens, p.cache_read_per_mtok)

    return CostBreakdown(
        input_cost=input_cost,
        output_cost=output_cost,
        cache_write_cost=cache_write_cost,
        cache_read_cost=cache_read_cost,
        total_cost=input_cost + output_cost + cache_write_cost + cache_read_cost,
        currency=p.currency,
        price_ref=PRICE_REF,
    )
