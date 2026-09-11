"""
ingestion/chunkers/naive.py  —  the BASELINE that BREAKS (on purpose).

Cuts every N characters, blind. It has no idea what the text means, so it will
happily slice through the middle of a sentence, a table row, or an Arabic word.

We build it NOT because it's good, but because it's the baseline to MEASURE
against. Later the eval suite runs the same golden questions against naive vs
structure_aware and prints the delta ("recall@5 0.68 -> 0.89"). You can't prove
structure-aware is better without the naive number to beat.

Selected by config/rag.yaml -> ingestion.chunker: naive
"""

from __future__ import annotations

from ingestion.chunkers.base import Chunker
from ingestion.types import Chunk, ExtractedDoc


class NaiveChunker(Chunker):
    name = "naive"

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100) -> None:
        # chunk_size / overlap are in CHARACTERS here (a real system counts tokens;
        # chars keep the baseline dead simple — which is the point of the baseline).
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, doc: ExtractedDoc) -> list[Chunk]:
        chunks: list[Chunk] = []
        idx = 0
        step = self.chunk_size - self.chunk_overlap
        for page in doc.pages:
            text = page.text
            # Slide a fixed window across the raw text. Zero awareness of structure.
            for start in range(0, len(text), step):
                piece = text[start:start + self.chunk_size].strip()
                if not piece:
                    continue
                chunks.append(Chunk(
                    text=piece,
                    chunk_index=idx,
                    page_number=page.page_number,
                    source_filename=doc.source_filename,
                ))
                idx += 1
        return chunks