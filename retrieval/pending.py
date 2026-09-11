"""
retrieval/pending.py  —  strategies NOT built yet, declared honestly.

These are real switches in rag.yaml (crag, graph, agentic, query_transform) but
building them now would be dishonest: they depend on tools we haven't built, or
they're locked-until-an-eval-proves-need per PRODUCT.md §4.

Rather than fake them, each raises a clear NotImplementedError explaining WHAT it
needs and WHEN we'll build it. The retriever factory can still list them, so the
config surface stays complete — but you can't accidentally run an empty strategy.

This is the "cheap-and-broad first, expensive-and-specific last, only when a
measurement calls for it" rule, encoded so future-you can't skip it.
"""

from __future__ import annotations

from retrieval.base import RetrievedChunk, Retriever


class _NotYet(Retriever):
    reason: str = "not implemented"

    def retrieve(self, question: str, top_k: int) -> list[RetrievedChunk]:
        raise NotImplementedError(self.reason)


class QueryTransformRetriever(_NotYet):
    name = "query_transform"
    reason = (
        "query_transform (rewrite / HyDE) needs the LLM box (it uses an LLM to "
        "rewrite the question BEFORE searching). Build after the Generation box."
    )


class CragRetriever(_NotYet):
    name = "crag"
    reason = (
        "CRAG (Corrective RAG) needs the LLM box: it retrieves, then uses an LLM "
        "to GRADE the chunks and re-search if they're weak. Build after Generation, "
        "and only if evals show naive/hybrid+rerank plateau below target."
    )


class GraphRetriever(_NotYet):
    name = "graph"
    reason = (
        "GraphRAG is LOCKED (PRODUCT.md §4): expensive to build + run. Turn on the "
        "graph.enabled switch and build ONLY when an eval proves connect-the-dots "
        "questions fail on hybrid+rerank."
    )


class AgenticRetriever(_NotYet):
    name = "agentic"
    reason = (
        "Agentic retrieval is LOCKED: the most expensive strategy (multi-step "
        "decompose->route->reflect, many LLM calls). Last resort, eval-gated."
    )