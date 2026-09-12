"""
evals/metrics.py  —  the measuring sticks the lab uses to score a run.

runner.py imports THREE things from here, one per question it can ask:

  recall_at_k   -> "did retrieval bring back the right pages?"  (retrieval quality)
  percentile    -> "what is the p95 latency?"                   (speed, PRODUCT.md)
  LLMJudge      -> "is the ANSWER faithful + relevant?"         (answer quality)

Golden rule of RAG eval (repeated all over the learning log): measure RETRIEVAL
and ANSWER separately. recall_at_k judges the retriever alone (no LLM involved);
LLMJudge judges the generated answer. A bad number in one is a different disease
than a bad number in the other, and you fix them in different places.

This module is pure + tiny on purpose: recall_at_k and percentile are plain math
(unit-testable, no I/O); only LLMJudge touches an LLM, and it does so through the
same LLMClient Port everything else uses, so it swaps Ollama <-> Claude by config.
"""

from __future__ import annotations

import re
from math import ceil, floor

from llm.client import LLMClient


# =============================================================================
# 1) recall_at_k  —  retrieval quality, measured WITHOUT the LLM.
# =============================================================================
def recall_at_k(retrieved_pages: list[int], expected_pages: list[int]) -> float:
    """Fraction of the EXPECTED pages that actually showed up in what was retrieved.

    recall = |retrieved ∩ expected| / |expected|

      expected [4, 5], retrieved [4, 9]   -> found 4, missed 5      -> 0.5
      expected [4, 5], retrieved [4, 5, 9]-> found both             -> 1.0
      expected [4],    retrieved [9]       -> missed it             -> 0.0

    The `k` is implicit: `retrieved_pages` is already the top-k the retriever
    returned, so this is recall@k for whatever k the runner passed.

    An empty `expected_pages` means a malformed golden item (nothing to find) —
    we return 0.0 rather than dividing by zero, so a broken golden row fails
    loudly in the scorecard instead of silently counting as a perfect score.
    (This is exactly the bug the previous chat hit: a golden row pointing at a
    page that didn't exist.)
    """
    expected = set(expected_pages)
    if not expected:
        return 0.0
    found = expected & set(retrieved_pages)
    return len(found) / len(expected)


# =============================================================================
# 2) percentile  —  the p95 latency measuring stick.
# =============================================================================
def percentile(values: list[float], p: float) -> float:
    """The value below which `p` percent of the data falls (linear interpolation).

    Same method as numpy's default so our p95 matches a spreadsheet's. The mean
    hides the bad tail (you can average 1s while five users wait 30s); p95 catches
    it — which is why PRODUCT.md targets p95, not the mean.

      percentile([1, 2, 3, 4], 95) -> 3.85   (between the 3rd and 4th value)

    Empty input -> 0.0 (no requests measured yet).
    """
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    # rank is a fractional index into the sorted list, 0..len-1
    rank = (p / 100.0) * (len(xs) - 1)
    lo, hi = floor(rank), ceil(rank)
    if lo == hi:
        return xs[int(rank)]
    frac = rank - lo
    return xs[lo] + (xs[hi] - xs[lo]) * frac


# =============================================================================
# 3) LLMJudge  —  answer quality, scored by an LLM (faithfulness + relevance).
# =============================================================================
# One prompt template per metric. Untrusted content (context / answer / question)
# is wrapped in tags so it can never be read as instructions (Step 2 delimiter
# defense). Each judge must return ONE number in [0, 1] and nothing else.
_FAITHFULNESS_SYSTEM = (
    "You are a strict, literal evaluator. You judge whether an ANSWER is fully "
    "supported by a CONTEXT. A claim is supported only if the CONTEXT states it. "
    "Do not use outside knowledge. Reply with ONE number between 0.0 and 1.0 and "
    "nothing else: 1.0 = every claim is supported, 0.0 = the answer contradicts or "
    "invents facts not in the context."
)
_RELEVANCE_SYSTEM = (
    "You are a strict evaluator. You judge how well an ANSWER addresses a QUESTION, "
    "regardless of whether it is factually correct. Reply with ONE number between "
    "0.0 and 1.0 and nothing else: 1.0 = fully answers what was asked, 0.0 = "
    "off-topic or non-responsive."
)

# Grab the first 0.xx / 1.0 / 0 / 1 style number anywhere in the reply.
_SCORE_RE = re.compile(r"(\d+(?:\.\d+)?)")


class LLMJudge:
    """LLM-as-a-judge: uses the same LLMClient Port as the rest of the app.

    Kept deliberately thin — two grounded, temperature-0 calls that each come
    back as a single number we parse and clamp to [0, 1]. If the model returns
    something unparseable, we score 0.0 (a judge that can't answer is a failing
    signal, not a crash that kills the whole eval run).
    """

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def faithfulness(self, context: str, answer: str) -> float:
        """Is every claim in `answer` supported by `context`? (anti-hallucination)"""
        user = (
            f"<context>\n{context}\n</context>\n\n"
            f"<answer>\n{answer}\n</answer>\n\n"
            "Score the faithfulness of the answer to the context."
        )
        return self._score(_FAITHFULNESS_SYSTEM, user)

    def answer_relevance(self, question: str, answer: str) -> float:
        """Does `answer` actually address `question`?"""
        user = (
            f"<question>\n{question}\n</question>\n\n"
            f"<answer>\n{answer}\n</answer>\n\n"
            "Score how well the answer addresses the question."
        )
        return self._score(_RELEVANCE_SYSTEM, user)

    def _score(self, system: str, user: str) -> float:
        resp = self.llm.complete(system, user, temperature=0.0)
        return self._parse_score(resp.text)

    @staticmethod
    def _parse_score(text: str) -> float:
        """Extract the first number from the reply and clamp to [0, 1]."""
        m = _SCORE_RE.search(text or "")
        if not m:
            return 0.0
        try:
            value = float(m.group(1))
        except ValueError:
            return 0.0
        # clamp — a model that says "1.0" or wanders to "5" both land in range
        return max(0.0, min(1.0, value))
