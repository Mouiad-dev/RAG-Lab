"""
retrieval/factory.py  —  builds the retriever the config asks for.

The ONE place that knows every strategy. Reads config/rag.yaml's retrieval.* block
and returns the right Retriever, optionally wrapped in a reranker.

Strategy map (all real now):
    naive           -> dense vector search
    hybrid          -> dense + keyword(FTS) + RRF
    query_transform -> rewrite | hyde  (wraps hybrid; needs LLM)
    crag            -> retrieve + LLM-grade + correct  (wraps hybrid; needs LLM)
    graph           -> multi-hop neighbour expansion (wraps hybrid)   [LOCKED default]
    agentic         -> decompose -> retrieve per sub-q -> merge (needs LLM) [LOCKED]
  + rerank.enabled  -> wrap any of the above in a cross-encoder reranker

The advanced ones need an LLM, so the factory takes an optional llm. If a mode
needs the LLM and none was given, it raises a clear error (never a silent stub).

Change config, not code -> re-run the SAME eval suite -> read the delta. The lab.
"""

from __future__ import annotations

from core.repository import DocumentRepository
from embeddings.embedder import Embedder
from llm.client import LLMClient
from retrieval.agentic import AgenticRetriever
from retrieval.base import Retriever
from retrieval.crag import CragRetriever
from retrieval.graph import GraphRetriever
from retrieval.hybrid import HybridRetriever
from retrieval.naive import NaiveRetriever
from retrieval.query_transform import QueryTransformRetriever
from retrieval.rerank import CrossEncoderReranker, NoOpReranker


def _need_llm(mode: str, llm: LLMClient | None) -> LLMClient:
    if llm is None:
        raise ValueError(
            f"retrieval.mode={mode!r} needs an LLM. Pass llm=build_llm(cfg) to "
            f"build_retriever, and make sure the ollama box is running."
        )
    return llm


def build_retriever(
    cfg: dict,
    repo: DocumentRepository,
    embedder: Embedder,
    llm: LLMClient | None = None,
) -> Retriever:
    """Construct the retriever described by cfg['retrieval']."""
    r = cfg.get("retrieval", {})
    mode = r.get("mode", "naive")
    top_k = r.get("top_k", 5)

    def make_hybrid() -> Retriever:
        hy = r.get("hybrid", {})
        return HybridRetriever(
            repo, embedder,
            rrf_k=hy.get("rrf_k", 60),
            candidate_n=top_k * 4,   # retrieve wider than we return
        )

    # --- base strategy ---
    if mode == "naive":
        base: Retriever = NaiveRetriever(repo, embedder)

    elif mode == "hybrid":
        base = make_hybrid()

    elif mode == "query_transform":
        qt = r.get("query_transform", "rewrite")
        if qt == "none":                     # 'none' = don't transform = plain hybrid
            base = make_hybrid()
        else:
            base = QueryTransformRetriever(make_hybrid(), _need_llm(mode, llm), mode=qt)

    elif mode == "crag":
        base = CragRetriever(make_hybrid(), _need_llm(mode, llm))

    elif mode == "graph":
        if not r.get("graph", {}).get("enabled", False):
            raise ValueError("retrieval.mode=graph but retrieval.graph.enabled is false (LOCKED).")
        base = GraphRetriever(make_hybrid(), repo, embedder,
                              hop_window=r.get("graph", {}).get("hop_window", 1))

    elif mode == "agentic":
        if not r.get("agentic", {}).get("enabled", False):
            raise ValueError("retrieval.mode=agentic but retrieval.agentic.enabled is false (LOCKED).")
        base = AgenticRetriever(make_hybrid(), _need_llm(mode, llm))

    else:
        raise ValueError(f"unknown retrieval.mode: {mode!r}")

    # --- optional rerank wrapper (composes with ANY strategy) ---
    rr = r.get("rerank", {})
    if rr.get("enabled", False):
        return CrossEncoderReranker(base, candidate_n=rr.get("top_n", 5) * 4)
    return NoOpReranker(base)