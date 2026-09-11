"""
retrieval/factory.py  —  builds the retriever the config asks for.

This is the ONE place that knows every strategy. It reads config/rag.yaml's
retrieval.* block and returns the right Retriever, optionally wrapped in a
reranker. Everything else depends only on the Retriever interface.

To compare strategies you change config, not code:
    retrieval.mode: naive        -> NaiveRetriever
    retrieval.mode: hybrid       -> HybridRetriever  (dense + BM25/FTS + RRF)
    retrieval.rerank.enabled: true  -> wrap the above in CrossEncoderReranker
    retrieval.mode: crag|graph|agentic -> pending (raise a clear "build me later")

Then re-run the SAME eval suite and read the delta. That's the lab.
"""

from __future__ import annotations

from core.repository import DocumentRepository
from embeddings.embedder import Embedder
from retrieval.base import Retriever
from retrieval.hybrid import HybridRetriever
from retrieval.naive import NaiveRetriever
from retrieval.pending import (
    AgenticRetriever,
    CragRetriever,
    GraphRetriever,
    QueryTransformRetriever,
)
from retrieval.rerank import CrossEncoderReranker, NoOpReranker


def build_retriever(
    cfg: dict, repo: DocumentRepository, embedder: Embedder
) -> Retriever:
    """Construct the retriever described by cfg['retrieval']."""
    r = cfg.get("retrieval", {})
    mode = r.get("mode", "naive")

    # --- base strategy ---
    if mode == "naive":
        base: Retriever = NaiveRetriever(repo, embedder)
    elif mode == "hybrid":
        hy = r.get("hybrid", {})
        base = HybridRetriever(
            repo, embedder,
            rrf_k=hy.get("rrf_k", 60),
            candidate_n=r.get("top_k", 5) * 4,   # retrieve wider than we return
        )
    elif mode == "query_transform":
        base = QueryTransformRetriever()
    elif mode == "crag":
        base = CragRetriever()
    elif mode == "graph":
        base = GraphRetriever()
    elif mode == "agentic":
        base = AgenticRetriever()
    else:
        raise ValueError(f"unknown retrieval.mode: {mode!r}")

    # --- optional rerank wrapper ---
    rr = r.get("rerank", {})
    if rr.get("enabled", False):
        return CrossEncoderReranker(base, candidate_n=rr.get("top_n", 5) * 4)
    return NoOpReranker(base)