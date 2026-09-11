"""
retrieval/hybrid.py  —  the KEY upgrade: dense + keyword, fused by RRF.

WHY hybrid is the most important strategy for THIS project (locked decision):
  - Dense (pgvector) understands MEANING — great for paraphrases, cross-language.
  - Keyword (FTS/BM25) catches LITERAL terms — exact codes ('JWT'), Arabic words
    dense can smear, section numbers ('البند ٧-أ').
For a bilingual, accountable user, missing a literal term is a real failure, so
the keyword leg is not optional. RRF merges the two rank lists (see fusion.py).

Flow (Phase B):
  question
    ├─ dense:   embed -> pgvector cosine top_n  ──┐
    ├─ keyword: FTS ts_rank_cd top_n            ──┤─ RRF fuse -> take top_k
                                                  ┘

Retrieve WIDE (candidate_n per leg), fuse, then cut to top_k. That "retrieve wide,
narrow after" pattern is also what reranking will build on next.

Selected by config/rag.yaml -> retrieval.mode: hybrid
"""

from __future__ import annotations

from core.repository import DocumentRepository
from embeddings.embedder import Embedder
from retrieval.base import RetrievedChunk, Retriever
from retrieval.fusion import reciprocal_rank_fusion


def _key(row) -> tuple[str, int]:
    """Stable identity for a chunk across the two lists: (filename, chunk_index)."""
    # row = (text, source_filename, page_number, chunk_index, score)
    return (row[1], row[3])


class HybridRetriever(Retriever):
    name = "hybrid"

    def __init__(
        self,
        repo: DocumentRepository,
        embedder: Embedder,
        rrf_k: int = 60,
        candidate_n: int = 20,
    ) -> None:
        self.repo = repo
        self.embedder = embedder
        self.rrf_k = rrf_k
        # how many candidates to pull from EACH leg before fusing. Wider = better
        # recall, slower. 20 is a safe default per the 2026 sources (20 small corpus).
        self.candidate_n = candidate_n

    def retrieve(self, question: str, top_k: int) -> list[RetrievedChunk]:
        # --- leg 1: dense (meaning) ---
        qvec = self.embedder.embed_one(question)
        dense_rows = self.repo.search_by_vector(qvec, self.candidate_n)

        # --- leg 2: keyword (literal) ---
        kw_rows = self.repo.search_by_keyword(question, self.candidate_n)

        # --- remember each chunk's full row by key, for building results later ---
        by_key: dict[tuple[str, int], tuple] = {}
        for row in dense_rows:
            by_key[_key(row)] = row
        for row in kw_rows:
            by_key.setdefault(_key(row), row)

        # --- fuse by RANK, not score (RRF) ---
        dense_ranking = [_key(r) for r in dense_rows]
        kw_ranking = [_key(r) for r in kw_rows]
        fused = reciprocal_rank_fusion(
            [dense_ranking, kw_ranking], k=self.rrf_k
        )  # {key: fused_score}

        # --- sort by fused score desc, take top_k, map to RetrievedChunk ---
        top_keys = sorted(fused, key=lambda kk: fused[kk], reverse=True)[:top_k]
        results: list[RetrievedChunk] = []
        for kk in top_keys:
            text, source_filename, page_number, chunk_index, _leg_score = by_key[kk]
            results.append(RetrievedChunk(
                text=text,
                source_filename=source_filename,
                page_number=page_number,
                chunk_index=chunk_index,
                score=fused[kk],          # report the FUSED score
            ))
        return results