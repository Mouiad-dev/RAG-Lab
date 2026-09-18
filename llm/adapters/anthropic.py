"""Anthropic adapter — the demo backend, via the official SDK.

Maps the SDK's Message + usage into OUR LLMResponse; no anthropic.types.* escapes
this file. Applies the Step-1 discipline: explicit timeout, check `stop_reason`
(truncation/refusal is surfaced, never shipped as garbage). API key comes from the
ANTHROPIC_API_KEY env var (loaded from .env into the container).

Note on sampling: modern Claude models (Opus 5, Sonnet 5, ...) reject `temperature`
and other sampling params (HTTP 400), so we do NOT forward it. Determinism is the
model default; the `temperature` kwarg is accepted to satisfy the Protocol but
intentionally ignored here.
"""

from __future__ import annotations

import os
import time

import anthropic

from ..ports import LLMResponse
from ..registry import register_provider

# TODO: later to change this be controlled by admin
DEFAULT_MODEL = "claude-haiku-4-5"


class TruncatedResponseError(RuntimeError):
    """Raised when the model hit max_tokens — output is incomplete, don't trust it."""


class RefusalError(RuntimeError):
    """Raised when the model refused the request (safety)."""


@register_provider("anthropic")
class AnthropicClient:
    provider = "anthropic"

    def __init__(self, model: str | None = None, *, timeout: float = 60.0):
        self.model = model or DEFAULT_MODEL
        # SDK reads ANTHROPIC_API_KEY from the environment. Org-scoped keys also need
        # a workspace id header — supplied via ANTHROPIC_WORKSPACE_ID if set.
        default_headers = {}
        workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
        if workspace_id:
            default_headers["anthropic-workspace-id"] = workspace_id
        self._client = anthropic.Anthropic(
            timeout=timeout, default_headers=default_headers or None
        )

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0.0,  # accepted for the Protocol; not forwarded (see module note)
        max_tokens: int = 1024,
        purpose: str = "",
        prompt_ref: str = "",
    ) -> LLMResponse:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        started = time.perf_counter()
        msg = self._client.messages.create(**kwargs)
        latency_ms = int((time.perf_counter() - started) * 1000)

        # Discipline: never ship a truncated or refused response as if it were good.
        if msg.stop_reason == "max_tokens":
            raise TruncatedResponseError(
                f"Response truncated at max_tokens={max_tokens} (purpose={purpose!r})"
            )
        if msg.stop_reason == "refusal":
            raise RefusalError(f"Model refused (purpose={purpose!r})")

        text = "".join(block.text for block in msg.content if block.type == "text")

        usage = msg.usage
        return LLMResponse(
            text=text,
            model=msg.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            stop_reason=msg.stop_reason,
            latency_ms=latency_ms,
        )
