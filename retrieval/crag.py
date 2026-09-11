"""
retrieval/crag.py  —  Corrective RAG (needs LLM).

Naive/hybrid retrieve and TRUST the result. CRAG adds a self-check: after
retrieving, it asks an LLM to GRADE whether the chunks actually look relevant to
the question. If they're weak, it CORRECTS — re-searches with a rewritten query —
instead of feeding garbage to the answer step.

Flow:
    retrieve (base) -> LLM grades relevance (0..1)
       high  -> use as-is
       low   -> rewrite the query, retrieve again, use the better set

Why it matters for an accountable user: it's a guardrail against "confidently
answering from irrelevant chunks." Cost: 1 extra LLM call per query (the grader),
sometimes 2 (rewrite + re-retrieve). So it's eval-gated: turn on only if evals
show naive/hybrid retrieve weak chunks on some cohort.

Config: retrieval.mode: crag
"""

from __future__ import annotations

from llm.client import LLMClient
from retrieval.base import RetrievedChunk, Retriever

GRADE_SYS = "You grade whether retrieved text is relevant to a question. Output only a number 0.0-1.0."
GRADE_USER = "Question: {q}\n\nRetrieved text:\n{ctx}\n\nRelevance score (0.0-1.0):"

REWRITE_SYS = "You rewrite questions into better search queries. Output only the query."
REWRITE_USER = "The search for this question returned weak results. Rewrite it to retrieve better:\n{q}"


class CragRetriever(Retriever):
    name = "crag"

    def __init__(
        self,
        base: Retriever,
        llm: LLMClient,
        relevance_threshold: float = 0.6,
    ) -> None:
        self.base = base
        self.llm = llm
        # below this graded score, the retrieval is considered weak -> correct it.
        self.relevance_threshold = relevance_threshold

    def _grade(self, question: str, chunks: list[RetrievedChunk]) -> float:
        if not chunks:
            return 0.0
        ctx = "\n\n".join(c.text for c in chunks[:3])   # grade the top few
        r = self.llm.complete(GRADE_SYS, GRADE_USER.format(q=question, ctx=ctx), temperature=0.0)
        return _parse_score(r.text)

    def retrieve(self, question: str, top_k: int) -> list[RetrievedChunk]:
        # 1) first attempt
        chunks = self.base.retrieve(question, top_k)
        # 2) self-grade
        score = self._grade(question, chunks)
        if score >= self.relevance_threshold:
            return chunks
        # 3) CORRECT: rewrite the query and retrieve again
        rw = self.llm.complete(REWRITE_SYS, REWRITE_USER.format(q=question), temperature=0.0)
        better_query = rw.text.strip() or question
        corrected = self.base.retrieve(better_query, top_k)
        # keep whichever set graded better (cheap: re-grade the corrected set)
        corrected_score = self._grade(question, corrected)
        return corrected if corrected_score >= score else chunks


def _parse_score(text: str) -> float:
    import re
    for token in re.findall(r"[0-1](?:\.\d+)?", text):
        v = float(token)
        if 0.0 <= v <= 1.0:
            return v
    return 0.0