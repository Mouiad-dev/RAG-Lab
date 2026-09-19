"""The chunking boundary (Port) — sibling of the LLM and Embeddings Ports.

A chunker cuts one document's extracted text into small, retrievable slices. We
can't feed a whole 50-page PDF to the LLM per question (attention cost, noise), so
we cut it into chunks, embed each, and later retrieve only the few nearest ones.

Two pieces, same shape as the other ports:

- `ChunkData` is a **Pydantic** in-memory boundary type — our OWN shape for "a slice
  of text", not a Django model. The chunker returns `ChunkData`; the pipeline maps
  those into `Chunk` ORM rows and embeds them. No chunker touches the DB.
- `Chunker` is a `typing.Protocol`: any object with `strategy` + `chunk(text)` IS a
  Chunker. Fixed-Size now; recursive/semantic/structure-aware later, all swappable.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ChunkData(BaseModel):
    """One produced slice, before it becomes a Chunk row or gets embedded."""

    text: str
    ordinal: int                       # position within the document (0, 1, 2, ...)
    page: int | None = None            # source page, when known (becomes the citation)
    token_count: int | None = None     # left None until a real tokenizer is wired
    metadata: dict = Field(default_factory=dict)  # heading/section/etc. (richer chunkers)


@runtime_checkable
class Chunker(Protocol):
    strategy: str

    def chunk(self, text: str) -> list[ChunkData]:
        """Cut extracted text into ordered slices. Ordinals must be 0..n-1."""
        ...
