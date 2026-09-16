"""Observability models.

Split by concern:
  - LLMCall  = the USAGE record: what happened (tokens, latency, model, purpose).
  - CallCost = the MONEY record (1:1 with a call): what it cost, broken down.

Cost is a correctness property (target <= $0.05/question), so every call is logged.
Both rows are written together (Step 1.5) from an in-memory LLMResponse: the dollar
amounts are COMPUTED at call time via the code-side price book and snapshotted here,
so historical costs stay accurate even if prices change. Every LLMCall has exactly
one CallCost (Ollama calls get an all-zero cost).
"""

from django.db import models


class LLMCall(models.Model):
    """USAGE: one row per LLM call — tokens and timing, no money."""

    provider = models.CharField(max_length=50)   # "ollama" / "anthropic"
    model = models.CharField(max_length=100)     # e.g. "qwen2.5", "claude-..."
    purpose = models.CharField(max_length=50, blank=True)  # answer/grading/advisor/hyde

    # Pointer to the versioned prompt (the PromptTemplate model arrives Phase 2/4).
    prompt_ref = models.CharField(max_length=100, blank=True)  # e.g. "answer@v3"

    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    # Prompt-cache accounting (Anthropic): writing the cache vs reusing it.
    cache_creation_tokens = models.PositiveIntegerField(default=0)  # cache WRITE
    cache_read_tokens = models.PositiveIntegerField(default=0)      # cache READ (hit)

    latency_ms = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider", "model"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"LLMCall({self.provider}/{self.model}, {self.purpose})"


class CallCost(models.Model):
    """MONEY: the cost breakdown for one LLMCall. Decimal (not float) — it's money."""

    llm_call = models.OneToOneField(
        LLMCall, on_delete=models.CASCADE, related_name="cost"
    )

    input_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    output_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    cache_write_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    cache_read_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    total_cost = models.DecimalField(max_digits=12, decimal_places=6, default=0)

    currency = models.CharField(max_length=3, default="USD")
    # Which price snapshot produced these numbers (auditability).
    price_ref = models.CharField(max_length=100, blank=True)  # e.g. "anthropic/claude@2026-01"

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"CallCost(call={self.llm_call_id}, {self.total_cost} {self.currency})"
