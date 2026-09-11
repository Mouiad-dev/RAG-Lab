"""
retrieval/rerank.py  —  reranking as a WRAPPER over any retriever.

Idea (from the cheat sheet's Re-Ranking section): "retrieve wide, rerank narrow."
A first-stage retriever (naive/hybrid) is fast but approximate. A reranker is slow
but precise — so we let the fast stage propose MANY candidates, then the reranker
re-scores just those and keeps the best top_k.

Design: a Reranker WRAPS a Retriever (decorator). The wrapped retriever pulls
candidate_n results; the reranker re-scores and trims to top_k. Because it's a
wrapper, it composes with ANY strategy — rerank(naive) or rerank(hybrid) — and is
toggled by config/rag.yaml -> retrieval.rerank.enabled.

Two rerankers:
  - NoOpReranker: pass-through (rerank disabled). Runs anywhere, keeps the pipeline
    working today.
  - CrossEncoderReranker: the real thing (sentence-transformers cross-encoder).
    Model is heavy, so it's built to run in the app box; declared but its scoring
    call is guarded so it fails clearly if the model isn't installed.
"""

from __future__ import annotations

from retrieval.base import RetrievedChunk, Retriever


class NoOpReranker(Retriever):
    """rerank disabled: return the base retriever's own top_k unchanged."""
    name = "rerank(off)"

    def __init__(self, base: Retriever) -> None:
        self.base = base

    def retrieve(self, question: str, top_k: int) -> list[RetrievedChunk]:
        return self.base.retrieve(question, top_k)


class CrossEncoderReranker(Retriever):
    """rerank enabled: pull candidate_n from base, re-score with a cross-encoder,
    keep top_k. A cross-encoder reads (question, chunk) TOGETHER, so it judges
    relevance far better than the first-stage vector similarity — at higher cost.
    """
    name = "rerank(cross-encoder)"

    def __init__(
        self,
        base: Retriever,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        candidate_n: int = 20,
    ) -> None:
        self.base = base
        self.model_name = model_name
        self.candidate_n = candidate_n
        self._model = None  # lazy-loaded on first use

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as e:
                raise RuntimeError(
                    "rerank.enabled=true needs sentence-transformers installed in "
                    "the app box (pip install sentence-transformers). It's heavy; "
                    "keep rerank off until an eval shows hybrid alone misses target."
                ) from e
            self._model = CrossEncoder(self.model_name)
        return self._model

    def retrieve(self, question: str, top_k: int) -> list[RetrievedChunk]:
        # 1) retrieve WIDE from the base strategy
        candidates = self.base.retrieve(question, self.candidate_n)
        if not candidates:
            return []
        # 2) re-score each (question, chunk) pair with the cross-encoder
        model = self._load()
        pairs = [(question, c.text) for c in candidates]
        scores = model.predict(pairs)
        # 3) attach new scores, sort desc, keep top_k
        for c, s in zip(candidates, scores):
            c.score = float(s)
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:top_k]