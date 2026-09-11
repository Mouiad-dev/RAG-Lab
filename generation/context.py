"""
generation/context.py  —  turn retrieved chunks into a grounded prompt.

Two jobs, both straight from the cheat sheet:

1. LOST IN THE MIDDLE (Section 10): LLMs attend to the START and END of a prompt,
   and forget the MIDDLE. So we DON'T just concatenate chunks in rank order — we
   place the highest-scoring chunks at the top AND bottom, weakest in the middle.

2. ANTI-HALLUCINATION PROMPT (Section 11): for an accountable user a confident
   wrong answer is worse than "I don't know". The system prompt enforces three
   rules: answer ONLY from context, say "I don't know" if it's not there, and cite.
"""

from __future__ import annotations

from retrieval.base import RetrievedChunk


def reorder_lost_in_the_middle(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Reorder by the 'primacy + recency' trick: best at the two ends.

    Given chunks sorted best->worst, produce an order like:
        [1st, 3rd, 5th, ... , 6th, 4th, 2nd]
    so ranks 1 and 2 land at the very top and very bottom of the context.
    """
    if len(chunks) <= 2:
        return chunks
    head: list[RetrievedChunk] = []   # gets odd-ranked (1st,3rd,5th...) -> top
    tail: list[RetrievedChunk] = []   # gets even-ranked (2nd,4th...) reversed -> bottom
    for i, c in enumerate(chunks):
        (head if i % 2 == 0 else tail).append(c)
    return head + list(reversed(tail))


SYSTEM_PROMPT = (
    "You are a document-grounded assistant for an accountable user.\n"
    "Follow these rules strictly:\n"
    "1. Answer ONLY using the provided context below. Do not use outside knowledge.\n"
    "2. If the context does not contain the answer, reply exactly: "
    "\"I don't know based on the provided documents.\"\n"
    "3. Cite the source of every claim as [source, p.N] using the citations given.\n"
    "4. Answer in the same language as the question (Arabic or English).\n"
    "Never invent facts. A wrong answer is worse than admitting you don't know."
)


def build_user_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    """Assemble the context block (reordered) + the question into the user turn."""
    ordered = reorder_lost_in_the_middle(chunks)
    blocks = []
    for c in ordered:
        # each block is clearly labelled with its citation so the LLM can cite it
        blocks.append(f"[{c.citation()}]\n{c.text}")
    context = "\n\n---\n\n".join(blocks)
    return (
        f"Context:\n{context}\n\n"
        f"---\n\n"
        f"Question: {question}\n\n"
        f"Answer (grounded only in the context above, with citations):"
    )