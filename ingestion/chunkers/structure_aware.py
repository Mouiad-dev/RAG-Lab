"""
ingestion/chunkers/structure_aware.py  —  the FIX.

Cuts on NATURAL boundaries, never through the middle of an idea:
  1. Split first on blank lines (paragraph / block boundaries).
  2. Keep whole markdown table rows ('|...|') together — never split a table.
  3. Greedily pack blocks into a chunk up to a size budget; start a new chunk
     rather than overflow. A block bigger than the budget stays whole (better a
     slightly big chunk than a table cut in half).

This is why Docling's markdown output matters: headings ('#') and table pipes
('|') are explicit seams we can respect. On the pdftotext fallback we still get
paragraph breaks, so it degrades sensibly.

Selected by config/rag.yaml -> ingestion.chunker: structure_aware
"""

from __future__ import annotations

from ingestion.chunkers.base import Chunker
from ingestion.types import Chunk, ExtractedDoc


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.endswith("|")


def _split_into_blocks(text: str) -> list[str]:
    """Group lines into blocks: consecutive table rows stay together as one block;
    everything else splits on blank lines into paragraph blocks."""
    blocks: list[str] = []
    buf: list[str] = []
    in_table = False

    def flush():
        nonlocal buf
        if buf:
            joined = "\n".join(buf).strip()
            if joined:
                blocks.append(joined)
        buf = []

    for line in text.splitlines():
        if _is_table_row(line):
            if not in_table:      # entering a table -> flush the prose before it
                flush()
                in_table = True
            buf.append(line)
        elif not line.strip():    # blank line -> paragraph boundary
            flush()
            in_table = False
        else:
            if in_table:          # table ended -> flush the table as its own block
                flush()
                in_table = False
            buf.append(line)
    flush()
    return blocks


class StructureAwareChunker(Chunker):
    name = "structure_aware"

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, doc: ExtractedDoc) -> list[Chunk]:
        chunks: list[Chunk] = []
        idx = 0
        for page in doc.pages:
            blocks = _split_into_blocks(page.text)
            current = ""
            for block in blocks:
                # If adding this block would overflow AND we already have content,
                # close the current chunk first (never split the block itself).
                if current and len(current) + len(block) + 2 > self.chunk_size:
                    chunks.append(self._make(current, idx, page, doc))
                    idx += 1
                    # small overlap: carry the tail of the previous chunk for context
                    tail = current[-self.chunk_overlap:] if self.chunk_overlap else ""
                    current = (tail + "\n\n" + block).strip()
                else:
                    current = (current + "\n\n" + block).strip() if current else block
            if current:
                chunks.append(self._make(current, idx, page, doc))
                idx += 1
        return chunks

    def _make(self, text: str, idx: int, page, doc: ExtractedDoc) -> Chunk:
        return Chunk(
            text=text,
            chunk_index=idx,
            page_number=page.page_number,
            source_filename=doc.source_filename,
        )