"""Sentence-Based chunker (#4) — the sentence is the atomic unit.

Unlike Recursive (which uses the sentence as one rung in a size-driven ladder and may
still end mid-sentence), this makes the SENTENCE sacred: every chunk is a whole number
of complete sentences, packed greedily up to `chunk_size`, with an optional
sentence-level overlap. Clean, complete passages embed more coherently and make better
citations. This is also the prerequisite for Semantic chunking (#5), which groups these
sentences by meaning.

The tricky part is segmentation itself. We hand-roll a regex splitter (Track Rule 01:
from scratch first). It is deliberately simple and has known gaps:

    NOTE(segmentation): this regex handles "Dr."/"e.g."/decimals/URLs via a small
    abbreviation + digit guard, and Arabic (؟ ! .) which has no capitalization. It will
    still mis-split exotic cases. The real upgrade — spaCy `.sents` / NLTK punkt /
    LlamaIndex SentenceSplitter — is a framework we adopt in the post-project tool pass,
    NOT mid-build.
"""

from __future__ import annotations

import re

from ..ports import ChunkData
from ..registry import register_chunker

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP_SENTENCES = 1

# Sentence-ending punctuation, EN + Arabic question mark. Followed by whitespace.
_BOUNDARY = re.compile(r"(?<=[.!?؟])\s+")

# Common abbreviations whose trailing period is NOT a sentence end.
_ABBREVIATIONS = {
    "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st", "vs", "etc",
    "e.g", "i.e", "no", "fig", "inc", "ltd", "co", "corp", "u.s", "u.k",
}


def _is_false_boundary(left: str) -> bool:
    """True if the period before a split is an abbreviation or a decimal, not an end."""
    left = left.rstrip()
    if not left.endswith("."):
        return False  # ! ? ؟ are reliable ends
    # decimal like "3.14" -> the char before the dot is a digit and so is the next token
    last_token = re.split(r"\s+", left)[-1].rstrip(".").lower()
    if last_token in _ABBREVIATIONS:
        return True
    if last_token and last_token[-1].isdigit():
        return True  # e.g. "3.14", section "1.2"
    if len(last_token) == 1 and last_token.isalpha():
        return True  # single-letter initial like "A." / "J."
    return False


def split_sentences(text: str) -> list[str]:
    """Split text into sentences (best-effort, hand-rolled). Pure function → unit-tested."""
    text = text.strip()
    if not text:
        return []

    sentences: list[str] = []
    buffer = ""
    # Walk candidate boundaries; re-join across false boundaries (abbrev/decimal).
    parts = _BOUNDARY.split(text)
    for part in parts:
        candidate = f"{buffer} {part}".strip() if buffer else part
        if _is_false_boundary(candidate):
            buffer = candidate  # not a real end; keep accumulating
        else:
            sentences.append(candidate)
            buffer = ""
    if buffer:
        sentences.append(buffer)
    return [s for s in (s.strip() for s in sentences) if s]


@register_chunker("sentence")
class SentenceChunker:
    strategy = "sentence"

    def __init__(
        self,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap_sentences: int = DEFAULT_OVERLAP_SENTENCES,
    ):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap_sentences < 0:
            raise ValueError("overlap_sentences must be >= 0")
        self.chunk_size = chunk_size
        self.overlap_sentences = overlap_sentences

    def _hard_slice(self, sentence: str) -> list[str]:
        """Last resort: a single sentence longer than chunk_size."""
        return [sentence[i : i + self.chunk_size] for i in range(0, len(sentence), self.chunk_size)]

    def chunk(self, text: str) -> list[ChunkData]:
        sentences = split_sentences(text)
        if not sentences:
            return []

        chunks: list[str] = []
        current: list[str] = []  # sentences accumulated for the current chunk

        def flush() -> None:
            if current:
                chunks.append(" ".join(current))

        for sentence in sentences:
            if len(sentence) > self.chunk_size:
                # oversized single sentence: flush what we have, then hard-slice it
                flush()
                current = []
                chunks.extend(self._hard_slice(sentence))
                continue

            projected = (" ".join(current + [sentence])).strip()
            if current and len(projected) > self.chunk_size:
                flush()
                # seed the next chunk with the last N sentences for overlap context,
                # but only if that seed still leaves room for this sentence.
                seed = current[-self.overlap_sentences :] if self.overlap_sentences else []
                current = seed if len(" ".join(seed + [sentence])) <= self.chunk_size else []
            current.append(sentence)
        flush()

        result: list[ChunkData] = []
        for piece in chunks:
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
                        "overlap_sentences": self.overlap_sentences,
                    },
                )
            )
        return result
