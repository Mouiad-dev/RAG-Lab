"""
retrieval/fusion.py  —  Reciprocal Rank Fusion (RRF).

The problem: hybrid search runs TWO searches — dense (meaning) and keyword
(literal) — and gets TWO ranked lists. How do you merge them into one? You can't
just compare their scores: cosine similarity (0..1) and ts_rank_cd (unbounded)
live on different scales. Comparing them directly is apples vs oranges.

RRF's trick: IGNORE the scores, use only the RANK (position). A chunk's fused
score is the sum, over each list it appears in, of 1/(k + rank).

    fused_score(chunk) = Σ  1 / (k + rank_in_list)

- rank is 1-based (1 = top of that list).
- k is a smoothing constant. k=60 is the paper's standard default (Cormack 2009),
  and every source says "leave k=60 alone" — RRF is famously insensitive to it.
- A chunk that ranks high in BOTH lists gets contributions from both -> rises to
  the top. That's the "consensus" behaviour we want: each method covers the
  other's blind spot (dense misses exact 'JWT'; keyword misses paraphrases).

Why this is robust: no score normalization, no weight to tune, no commitment to
"trust dense more than keyword". The math surfaces cross-list agreement.
"""

from __future__ import annotations


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]], k: int = 60
) -> dict[str, float]:
    """Fuse several ranked lists of item-keys into one {key: fused_score} map.

    ranked_lists: each inner list is item keys in rank order (best first).
    Returns a dict you can sort by value descending to get the fused ranking.
    """
    fused: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, key in enumerate(ranked, start=1):   # 1-based rank
            fused[key] = fused.get(key, 0.0) + 1.0 / (k + rank)
    return fused