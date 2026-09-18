"""Test doubles — TEST SUITE ONLY. Never import from application code.

Per the no-fakes rule (§0): the product always uses a real LLM. A FakeLLM is
allowed only to test OUR logic (does the pipeline call complete()? does merging
work?) without a network or spend. It proves our code is right — it does not
pretend the product works.
"""

from __future__ import annotations

from .ports import LLMResponse


class FakeLLM:
    """A canned LLMClient. Satisfies the LLMClient Protocol structurally."""

    provider = "fake"
    model = "fake-1"

    def __init__(self, text: str = "fake answer") -> None:
        self._text = text
        self.calls: list[dict] = []  # spyable: what prompts were sent

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
        self.calls.append({"prompt": prompt, "system": system, "purpose": purpose})
        return LLMResponse(
            text=self._text,
            model=self.model,
            input_tokens=len(prompt.split()),
            output_tokens=len(self._text.split()),
            stop_reason="end_turn",
        )
