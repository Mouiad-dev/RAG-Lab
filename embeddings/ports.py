"""The embeddings boundary (Port) — twin of the LLM Port.

An embedder turns text into a fixed-length vector (a fingerprint of meaning). The
SAME embedder must be used at index-time and query-time, or the vectors live on
different maps and distances are meaningless.

`Embedder` is a typing.Protocol: any object with `embed`/`embed_query` + the three
attributes IS an Embedder — Ollama now, Voyage/OpenAI later, all interchangeable.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    provider: str
    model: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed many texts at once (ingestion embeds chunks in batches)."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        ...
