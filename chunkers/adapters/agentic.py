"""Agentic chunker (#8) — the LLM decides where the cuts go. Last and most expensive.

Instead of a size/structure/embedding rule, we number the sentences and ask an LLM which
consecutive sentences belong together, i.e. AFTER which indices a new chunk should start.
Reuses the existing `LLMClient` port (Ollama by default — no new tool). It introduces the
structured-output discipline we'll lean on in Phase 4:

  - ask for a strict JSON shape (a list of breakpoint indices),
  - VALIDATE it (parse, in-range, sorted, unique),
  - on any failure fall back to a DETERMINISTIC chunker — never ship garbage or crash the
    ingest because a small local model returned noise.

The LLM call is non-deterministic and network-bound, so the parse/validate/group logic is
pure (`parse_boundaries`, `group_by_boundaries`) and unit-tested with a FakeLLM.
"""

from __future__ import annotations

import json
import re

from ..ports import ChunkData
from ..registry import register_chunker
from .sentence import split_sentences

DEFAULT_CHUNK_SIZE = 1000
# TODO: why not using pydantic to force and validated or instructor framework
_SYSTEM = (
    "You segment text into topically-coherent chunks. You reply with ONLY JSON."
)


def _build_prompt(sentences: list[str], chunk_size: int) -> str:
    numbered = "\n".join(f"{i}: {s}" for i, s in enumerate(sentences))
    return (
        "Below are numbered sentences from a document. Group consecutive sentences that "
        "belong to the same topic. Return JSON of the form {\"breakpoints\": [i, j, ...]} "
        "where each number is the index of the LAST sentence of a group (a new chunk starts "
        f"after it). Keep each group under about {chunk_size} characters. Use only indices "
        f"0..{len(sentences) - 1}, strictly increasing.\n\n{numbered}"
    )


def parse_boundaries(raw: str, num_sentences: int) -> list[int]:
    """Extract + validate breakpoint indices from the model's reply. Pure function.

    Returns strictly-increasing, in-range indices in 0..num_sentences-2 (a break after the
    very last sentence is meaningless, so it's dropped). Raises ValueError on unusable output.
    """
    match = re.search(r"\{.*\}", raw, re.DOTALL)  # tolerate prose around the JSON
    if not match:
        raise ValueError("no JSON object in model output")
    data = json.loads(match.group(0))
    breaks = data.get("breakpoints", [])
    if not isinstance(breaks, list):
        raise ValueError("breakpoints is not a list")

    cleaned: list[int] = []
    for b in breaks:
        if not isinstance(b, int):
            raise ValueError(f"non-integer breakpoint: {b!r}")
        if 0 <= b <= num_sentences - 2 and (not cleaned or b > cleaned[-1]):
            cleaned.append(b)  # in range and strictly increasing
    return cleaned


def group_by_boundaries(sentences: list[str], breakpoints: list[int]) -> list[str]:
    """Join sentences into groups; a new group starts AFTER each breakpoint index. Pure."""
    groups: list[str] = []
    current: list[str] = []
    breaks = set(breakpoints)
    for i, s in enumerate(sentences):
        current.append(s)
        if i in breaks:
            groups.append(" ".join(current))
            current = []
    if current:
        groups.append(" ".join(current))
    return groups


@register_chunker("agentic")
class AgenticChunker:
    strategy = "agentic"

    def __init__(self, *, chunk_size: int = DEFAULT_CHUNK_SIZE, llm=None, fallback=None):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self.chunk_size = chunk_size
        self._llm = llm
        self._fallback = fallback

    @property
    def llm(self):
        if self._llm is None:
            from llm.factory import build_llm_client

            self._llm = build_llm_client()
        return self._llm

    @property
    def fallback(self):
        if self._fallback is None:
            from ..factory import build_chunker

            self._fallback = build_chunker(strategy="sentence", chunk_size=self.chunk_size)
        return self._fallback

    def _emit(self, groups: list[str], *, fallback_used: bool) -> list[ChunkData]:
        result: list[ChunkData] = []
        for piece in groups:
            piece = piece.strip()
            if not piece:
                continue
            result.append(
                ChunkData(
                    text=piece,
                    ordinal=len(result),
                    metadata={
                        "strategy": self.strategy,
                        "chunk_size": self.chunk_size,
                        "fallback": fallback_used,
                    },
                )
            )
        return result

    def chunk(self, text: str) -> list[ChunkData]:
        sentences = split_sentences(text)
        if not sentences:
            return []
        if len(sentences) == 1:
            return self._emit(sentences, fallback_used=False)

        try:
            response = self.llm.complete(
                _build_prompt(sentences, self.chunk_size),
                system=_SYSTEM,
                temperature=0.0,
                purpose="chunking",
                prompt_ref="agentic_chunk@v1",
            )
            breakpoints = parse_boundaries(response.text, len(sentences))
            groups = group_by_boundaries(sentences, breakpoints)
            return self._emit(groups, fallback_used=False)
        except Exception:
            # model returned garbage / call failed → deterministic fallback, never crash.
            fallback_chunks = self.fallback.chunk(text)
            return self._emit([c.text for c in fallback_chunks], fallback_used=True)
