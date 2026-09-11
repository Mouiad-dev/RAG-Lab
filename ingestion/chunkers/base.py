"""
ingestion/chunkers/base.py  —  the CHUNKER contract.

A chunker turns one ExtractedDoc into a list[Chunk]. That's the whole promise.
HOW it decides where to cut is the strategy's private business — and it's exactly
where naive RAG lives or dies (see naive.py vs structure_aware.py).

Every Chunk carries its own page_number + source_filename so citations survive
all the way to the final answer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ingestion.types import Chunk, ExtractedDoc


class Chunker(ABC):
    name: str = "base"

    @abstractmethod
    def chunk(self, doc: ExtractedDoc) -> list[Chunk]:
        """Split the document into retrievable Chunks, preserving citation metadata."""
        raise NotImplementedError