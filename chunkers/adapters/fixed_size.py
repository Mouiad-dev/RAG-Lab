"""Fixed-Size chunker — the simplest honest chunker, and the first to prove the pipeline.

It slides a fixed-width window over the text with a configurable overlap. Overlap
keeps a sentence that straddles a boundary from being split beyond recovery in BOTH
neighbouring chunks. This is the deliberately-naive baseline: it knows nothing about
sentences, paragraphs, or structure — later chunkers (recursive, semantic,
structure-aware) improve on it, and we'll measure the difference (PLAN_1.md: "never
blind fixed-cut" is the destination; this is the baseline we beat).

Character-based, not token-based: a real tokenizer arrives with a later chunker;
until then `token_count` stays None rather than faking a number.
"""

from __future__ import annotations

from ..ports import ChunkData
from ..registry import register_chunker

#TODO: to change this later depend on the chunk Strategy and rag Strategy
DEFAULT_CHUNK_SIZE = 1000   # characters per slice
DEFAULT_OVERLAP = 200       # characters shared with the previous slice


@register_chunker("fixed_size")
class FixedSizeChunker:
    strategy = "fixed_size"

    def __init__(
        self,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if not 0 <= overlap < chunk_size:
            raise ValueError("overlap must be >= 0 and < chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[ChunkData]:
        text = text.strip()
        if not text:
            return []

        step = self.chunk_size - self.overlap  # how far the window advances each time
        chunks: list[ChunkData] = []
        ordinal = 0
        start = 0
        while start < len(text):
            piece = text[start : start + self.chunk_size].strip()
            if piece:  # skip a window that was all whitespace
                chunks.append(
                    ChunkData(
                        text=piece,
                        ordinal=ordinal,
                        metadata={
                            "strategy": self.strategy,
                            "chunk_size": self.chunk_size,
                            "overlap": self.overlap,
                        },
                    )
                )
                ordinal += 1
            if start + self.chunk_size >= len(text):
                break  # this window already reached the end; no redundant tail chunk
            start += step
        return chunks
