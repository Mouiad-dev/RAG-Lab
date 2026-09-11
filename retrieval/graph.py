"""
retrieval/graph.py  —  GraphRAG-lite: multi-hop "connect the dots" (LOCKED by default).

Full GraphRAG builds a knowledge graph of entities/relations from the corpus (its
own heavy ingestion step). That's a big box we have NOT built. What we CAN build
now — and what captures the core benefit — is MULTI-HOP retrieval:

    hop 1: retrieve chunks for the question (base retriever)
    hop 2: from those chunks, pull neighbouring chunks (same document, adjacent
           pages / chunk_index) — the "connected" context around the hits
    merge, dedupe, return top_k

This helps "connect-the-dots" questions whose answer spans several nearby chunks
that a single-hop search would only partially grab. It's a cheap graph proxy using
document structure as the edges (no LLM, no graph DB).

⚠️ PRODUCT.md §4: graph is LOCKED — expensive/complex vs the payoff. This lite
version is here to learn from and to eval; a real entity-graph is only justified if
an eval proves connect-the-dots questions fail on hybrid+rerank.

Config: retrieval.mode: graph  (graph.enabled gate respected by the factory)
"""

from __future__ import annotations

from core.repository import DocumentRepository
from embeddings.embedder import Embedder
from retrieval.base import RetrievedChunk, Retriever


class GraphRetriever(Retriever):
    name = "graph"

    def __init__(
        self,
        base: Retriever,
        repo: DocumentRepository,
        embedder: Embedder,
        hop_window: int = 1,
    ) -> None:
        self.base = base
        self.repo = repo
        self.embedder = embedder
        # how many neighbouring chunks (by chunk_index) to pull around each hit.
        self.hop_window = hop_window

    def retrieve(self, question: str, top_k: int) -> list[RetrievedChunk]:
        # hop 1: normal retrieval
        seed = self.base.retrieve(question, top_k)

        # hop 2: expand to neighbours of each seed chunk (adjacent chunk_index in
        # the same document) — the "edges" of our lightweight graph.
        seen: set[tuple[str, int]] = {(c.source_filename, c.chunk_index) for c in seed}
        expanded: list[RetrievedChunk] = list(seed)
        for c in seed:
            for delta in range(-self.hop_window, self.hop_window + 1):
                if delta == 0:
                    continue
                neighbour_idx = c.chunk_index + delta
                if neighbour_idx < 0 or (c.source_filename, neighbour_idx) in seen:
                    continue
                row = self.repo.get_chunk(c.source_filename, neighbour_idx)
                if row is None:
                    continue
                text, source_filename, page_number, chunk_index = row
                expanded.append(RetrievedChunk(
                    text=text, source_filename=source_filename,
                    page_number=page_number, chunk_index=chunk_index,
                    score=c.score * 0.5,   # neighbours are supporting context, ranked below seeds
                ))
                seen.add((source_filename, neighbour_idx))

        # keep the strongest top_k after expansion (seeds naturally rank above neighbours)
        expanded.sort(key=lambda x: x.score, reverse=True)
        return expanded[:top_k]