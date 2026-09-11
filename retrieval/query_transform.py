"""
retrieval/query_transform.py  —  fix the QUESTION before searching (needs LLM).

Short/vague/messy questions retrieve badly. Two LLM-powered fixes, both wrapping a
base retriever (naive or hybrid) — the transform changes what we SEARCH WITH, not
how we search:

  REWRITE: LLM turns "how do I fix the container thing?" into a clean search query
           ("how to remove or stop a Docker container"). Cheap, one short LLM call.

  HyDE (Hypothetical Document Embeddings): LLM writes a short FAKE answer to the
        question, and we search with THAT instead of the question. Why it works
        (verified via papers): a question and its answer use different words, so
        question->document matching is weak; but a hypothetical answer looks like a
        real document, so answer->document matching lands closer in vector space.
        The fake answer can even be factually wrong — the encoder keeps the
        semantic SHAPE, which is what retrieval needs. The hypothetical is then
        thrown away; the real retrieved docs answer the question.

  ⚠️ 2026 note (verified): with strong hybrid + good embeddings, HyDE's lift has
     narrowed — it's a "test per cohort" tool, not a default. So: OFF unless an
     eval on vague-query cohorts proves it helps. Exactly why it's eval-gated.

Config: retrieval.mode: query_transform, retrieval.query_transform: rewrite | hyde
"""

from __future__ import annotations

from llm.client import LLMClient
from retrieval.base import RetrievedChunk, Retriever

REWRITE_SYS = "You rewrite user questions into clear search queries. Output only the rewritten query, nothing else."
REWRITE_USER = "Rewrite this into a concise search query:\n{q}"

HYDE_SYS = "You write a short, plausible passage that would answer the question, as if from a document. 2-3 sentences. Output only the passage."
HYDE_USER = "Question: {q}\n\nWrite a short hypothetical answer passage:"


class QueryTransformRetriever(Retriever):
    name = "query_transform"

    def __init__(self, base: Retriever, llm: LLMClient, mode: str = "rewrite") -> None:
        if mode not in {"rewrite", "hyde"}:
            raise ValueError("query_transform mode must be 'rewrite' or 'hyde'")
        self.base = base
        self.llm = llm
        self.mode = mode
        self.name = f"query_transform({mode})"

    def _transform(self, question: str) -> str:
        if self.mode == "rewrite":
            r = self.llm.complete(REWRITE_SYS, REWRITE_USER.format(q=question), temperature=0.0)
        else:  # hyde
            r = self.llm.complete(HYDE_SYS, HYDE_USER.format(q=question), temperature=0.0)
        transformed = r.text.strip()
        return transformed or question   # fall back to the original if the LLM returns nothing

    def retrieve(self, question: str, top_k: int) -> list[RetrievedChunk]:
        # transform the query, then hand it to the wrapped retriever unchanged.
        search_text = self._transform(question)
        return self.base.retrieve(search_text, top_k)