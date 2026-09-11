"""
retrieval/naive.py  —  the BASELINE retriever: pure dense vector search.

Flow (Phase B, runs every question):
    question --BGE-M3--> query vector --pgvector cosine top_k--> chunks

This is the simplest strategy and the baseline the eval suite measures against.
It's strong on MEANING ("how do I stop a container?" finds the stop-command chunk
even if worded differently) but weak on LITERAL keywords — especially Arabic terms
and exact codes like "JWT" or "البند ٧-أ", which dense embeddings can smear. That
weakness is exactly what the hybrid strategy (dense + BM25) will fix next, and the
eval delta will prove it.

Selected by config/rag.yaml -> retrieval.mode: naive
"""

from __future__ import annotations

from core.repository import DocumentRepository
from embeddings.embedder import Embedder
from retrieval.base import RetrievedChunk, Retriever


class NaiveRetriever(Retriever):
    name = "naive"

    def __init__(self, repo: DocumentRepository, embedder: Embedder) -> None:
        self.repo = repo
        self.embedder = embedder

    def retrieve(self, question: str, top_k: int) -> list[RetrievedChunk]:
        # 1) embed the QUESTION with the SAME embedder used at store-time.
        query_vector = self.embedder.embed_one(question)
        # 2) cosine top_k from pgvector (HNSW-indexed).
        rows = self.repo.search_by_vector(query_vector, top_k)
        # 3) map DB rows -> the uniform RetrievedChunk shape.
        return [
            RetrievedChunk(
                text=text,
                source_filename=source_filename,
                page_number=page_number,
                chunk_index=chunk_index,
                score=score,
            )
            for (text, source_filename, page_number, chunk_index, score) in rows
        ]