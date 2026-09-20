"""Semantic chunker (#5) — cut where the MEANING shifts, not where size/punctuation says.

The method (Greg Kamradt's "semantic splitting", also LlamaIndex SemanticSplitterNodeParser —
hand-built here per Track Rule 01):

  1. split into sentences (reuse 2.4's segmenter)
  2. embed every sentence (BGE-M3, one batch)
  3. cosine distance between each ADJACENT pair (1 - cosine similarity)
  4. a breakpoint wherever that distance exceeds a PERCENTILE threshold of all distances
     (data-adaptive: adjusts per document instead of a magic absolute number)
  5. group sentences between breakpoints; a `chunk_size` cap splits a too-large coherent run

Trade-off (honest): topically-pure chunks, but it embeds every sentence AT INGESTION —
expensive, and threshold-sensitive. Whether it beats recursive/sentence is a Phase-5 EVAL
question, not an assumption.

Design note: this is the first chunker that needs an Embedder to decide boundaries. The
`Chunker` Port signature stays `chunk(text)` — the embedder is a constructor dependency.
NOTE(cost): sentences are embedded here for boundary detection AND again in the pipeline's
embed stage when the final chunks are stored (double embed). Acceptable for the lab; reusing
them would couple the stages, so it's deferred.
"""

from __future__ import annotations

import math

from ..ports import ChunkData
from ..registry import register_chunker
from .sentence import split_sentences

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_BREAKPOINT_PERCENTILE = 90  # cut at distances above this percentile


def cosine_distance(a: list[float], b: list[float]) -> float:
    """1 - cosine similarity. Pure function (no numpy). 0 = identical direction, 2 = opposite."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - dot / (na * nb)


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (pct in 0..100). Pure function."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[int(rank)]
    frac = rank - low
    return ordered[low] * (1 - frac) + ordered[high] * frac


def find_breakpoints(distances: list[float], percentile: float) -> list[int]:
    """Indices i where a chunk boundary falls AFTER sentence i (before sentence i+1).

    `distances[i]` is the distance between sentence i and i+1. A breakpoint is any pair
    whose distance is strictly above the percentile threshold. Pure function → unit-tested
    without an embedder.
    """
    if not distances:
        return []
    threshold = _percentile(distances, percentile)
    return [i for i, d in enumerate(distances) if d > threshold]


@register_chunker("semantic")
class SemanticChunker:
    strategy = "semantic"

    def __init__(
        self,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        breakpoint_percentile: float = DEFAULT_BREAKPOINT_PERCENTILE,
        embedder=None,
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if not 0 <= breakpoint_percentile <= 100:
            raise ValueError("breakpoint_percentile must be in 0..100")
        self.chunk_size = chunk_size
        self.breakpoint_percentile = breakpoint_percentile
        self._embedder = embedder  # lazily built so importing this module needs no Ollama

    @property
    def embedder(self):
        if self._embedder is None:
            from embeddings.factory import build_embedder

            self._embedder = build_embedder()
        return self._embedder

    def _size_split(self, sentences: list[str]) -> list[str]:
        """Split one semantic group into <= chunk_size pieces, keeping whole sentences."""
        pieces: list[str] = []
        current: list[str] = []
        for s in sentences:
            projected = " ".join(current + [s])
            if current and len(projected) > self.chunk_size:
                pieces.append(" ".join(current))
                current = []
            current.append(s)
        if current:
            pieces.append(" ".join(current))
        return pieces

    def chunk(self, text: str) -> list[ChunkData]:
        sentences = split_sentences(text)
        if not sentences:
            return []
        if len(sentences) == 1:
            groups = [sentences]
        else:
            vectors = self.embedder.embed(sentences)
            distances = [
                cosine_distance(vectors[i], vectors[i + 1])
                for i in range(len(vectors) - 1)
            ]
            breaks = set(find_breakpoints(distances, self.breakpoint_percentile))
            groups, current = [], []
            for i, s in enumerate(sentences):
                current.append(s)
                if i in breaks:  # boundary AFTER sentence i
                    groups.append(current)
                    current = []
            if current:
                groups.append(current)

        result: list[ChunkData] = []
        for group in groups:
            for piece in self._size_split(group):  # enforce chunk_size cap
                piece = piece.strip()
                if not piece:
                    continue
                result.append(
                    ChunkData(
                        text=piece,
                        ordinal=len(result),
                        metadata={
                            "strategy": self.strategy,
                            "chunk_size": self.chunk_size,
                            "breakpoint_percentile": self.breakpoint_percentile,
                        },
                    )
                )
        return result
