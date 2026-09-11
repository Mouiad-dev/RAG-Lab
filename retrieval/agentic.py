"""
retrieval/agentic.py  —  multi-step agentic retrieval (LOCKED; most expensive).

The other strategies do ONE retrieval. An agent reasons about the question first:
if it's complex ("compare how images and containers each handle data"), it breaks
it into sub-questions, retrieves for EACH, then merges. This handles multi-part
questions a single search can't.

Flow:
    LLM decompose question -> [sub-q1, sub-q2, ...]
    for each sub-q: base.retrieve
    merge + dedupe -> top_k

⚠️ Most expensive strategy: 1 LLM call to decompose + N retrievals. PRODUCT.md §4:
LOCKED, last resort, eval-gated. Built here so it's on the shelf and measurable, not
because it's needed. Real agentic RAG adds reflection loops + tool routing — this is
the core (decompose->retrieve->merge) without the extra LLM round-trips.

Config: retrieval.mode: agentic
"""

from __future__ import annotations

from llm.client import LLMClient
from retrieval.base import RetrievedChunk, Retriever

DECOMPOSE_SYS = (
    "You break a complex question into 1-3 simple sub-questions, one per line. "
    "If the question is already simple, return it unchanged as a single line. "
    "Output only the sub-questions, no numbering, no extra text."
)
DECOMPOSE_USER = "Question: {q}\n\nSub-questions:"


class AgenticRetriever(Retriever):
    name = "agentic"

    def __init__(self, base: Retriever, llm: LLMClient, max_subqs: int = 3) -> None:
        self.base = base
        self.llm = llm
        self.max_subqs = max_subqs

    def _decompose(self, question: str) -> list[str]:
        r = self.llm.complete(DECOMPOSE_SYS, DECOMPOSE_USER.format(q=question), temperature=0.0)
        subs = [ln.strip("-• \t") for ln in r.text.splitlines() if ln.strip()]
        subs = [s for s in subs if s][: self.max_subqs]
        return subs or [question]   # fall back to the original question

    def retrieve(self, question: str, top_k: int) -> list[RetrievedChunk]:
        sub_questions = self._decompose(question)

        # retrieve for each sub-question, merge by best score per unique chunk
        best: dict[tuple[str, int], RetrievedChunk] = {}
        # each sub-q gets a share of the budget, but pull a few each so merge has choice
        per_sub = max(2, top_k)
        for sq in sub_questions:
            for c in self.base.retrieve(sq, per_sub):
                key = (c.source_filename, c.chunk_index)
                if key not in best or c.score > best[key].score:
                    best[key] = c

        merged = sorted(best.values(), key=lambda x: x.score, reverse=True)
        return merged[:top_k]