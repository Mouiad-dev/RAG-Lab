"""
retrieval/base.py  —  the RETRIEVER contract (Phase B).

A retriever answers: "given a question, which stored chunks are most relevant?"
Every strategy — naive vector, hybrid, CRAG, graph — returns the SAME shape
(list[RetrievedChunk]). Because the shape never changes, everything downstream
(context building, the LLM) never knows or cares which strategy ran.

That is what lets us flip retrieval.mode: naive -> hybrid and MEASURE the delta
with the same eval suite, without touching any other code. The contract is the seam.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    """One search hit, carrying everything needed to cite + rank it."""
    text: str
    source_filename: str        # citation: which document
    page_number: int            # citation: which page ("per p.4")
    chunk_index: int
    score: float                # relevance; higher = more relevant (we normalize per strategy)

    def citation(self) -> str:
        return f"{self.source_filename}, p.{self.page_number}"


class Retriever(ABC):
    name: str = "base"

    @abstractmethod
    def retrieve(self, question: str, top_k: int) -> list[RetrievedChunk]:
        """Return the top_k most relevant chunks for the question, best first."""
        raise NotImplementedError