"""Auto-advisor — profile a document and RECOMMEND a chunking strategy, with a reason.

Pattern: an Advisor service built on **transparent heuristics** (not a model) — explainable
and free (PLAN_1.md). It looks at cheap signals (length, Markdown structure, sentence size,
Arabic ratio) and suggests one of our registered chunkers, always with a human-readable
`reason`. The user (or a later upload UI) can accept or override; nothing is forced.

Kept as pure functions (`profile_text`, `recommend`) so the heuristics are unit-testable
with no DB/LLM; `advise(document)` is the thin wrapper that reads the file.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from chunkers.adapters.sentence import split_sentences

# --- thresholds (named so the heuristic reads like prose) ---
# TODO make those as configration
SHORT_DOC_CHARS = 400        # below this, one pass of whole sentences is plenty
LONG_SENTENCE_CHARS = 350    # avg sentence longer than this ⇒ prose without clear breaks
ARABIC_HEAVY_RATIO = 0.5     # majority-Arabic ⇒ budget the ~3× token tax
MIN_HEADINGS_FOR_STRUCTURE = 2

_HEADING = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)
_ARABIC = re.compile(r"[؀-ۿ]")
_ALPHA = re.compile(r"[^\W\d_]", re.UNICODE)


class DocumentProfile(BaseModel):
    char_count: int
    sentence_count: int
    avg_sentence_chars: float
    heading_count: int
    arabic_ratio: float

    @property
    def has_structure(self) -> bool:
        return self.heading_count >= MIN_HEADINGS_FOR_STRUCTURE


class ChunkingRecommendation(BaseModel):
    strategy: str
    reason: str
    profile: DocumentProfile


def profile_text(text: str) -> DocumentProfile:
    """Compute the cheap signals the heuristic needs. Pure function."""
    text = text or ""
    sentences = split_sentences(text)
    char_count = len(text)
    sentence_count = len(sentences)
    avg = (char_count / sentence_count) if sentence_count else float(char_count)
    alpha = _ALPHA.findall(text)
    arabic = _ARABIC.findall(text)
    arabic_ratio = (len(arabic) / len(alpha)) if alpha else 0.0
    return DocumentProfile(
        char_count=char_count,
        sentence_count=sentence_count,
        avg_sentence_chars=round(avg, 1),
        heading_count=len(_HEADING.findall(text)),
        arabic_ratio=round(arabic_ratio, 2),
    )


def recommend(profile: DocumentProfile) -> ChunkingRecommendation:
    """Map a profile to a chunker + reason. Transparent, ordered heuristics. Pure function."""
    if profile.has_structure:
        strategy = "document"
        reason = (
            f"{profile.heading_count} Markdown headings detected → structure-aware "
            "chunking keeps whole sections intact and yields heading-path citations."
        )
    elif profile.char_count < SHORT_DOC_CHARS:
        strategy = "sentence"
        reason = (
            f"short document ({profile.char_count} chars) → whole-sentence chunks read "
            "cleanly without over-splitting."
        )
    elif profile.arabic_ratio >= ARABIC_HEAVY_RATIO:
        strategy = "token"
        reason = (
            f"Arabic-heavy text (ratio {profile.arabic_ratio}) → token-aware chunking "
            "respects the ~3× token cost so chunks fit the real budget."
        )
    elif profile.avg_sentence_chars >= LONG_SENTENCE_CHARS:
        strategy = "semantic"
        reason = (
            f"long sentences (avg {profile.avg_sentence_chars} chars) and no headings → "
            "semantic chunking groups by meaning where punctuation gives weak boundaries."
        )
    else:
        strategy = "recursive"
        reason = (
            "unstructured prose → recursive chunking respects paragraph/sentence "
            "boundaries (the solid general-purpose default)."
        )
    return ChunkingRecommendation(strategy=strategy, reason=reason, profile=profile)


def advise(document) -> ChunkingRecommendation:
    """Profile a Document's extracted text and recommend a chunker. Thin wrapper."""
    from .extractors import extract_text  # lazy: keeps model import out of this module

    return recommend(profile_text(extract_text(document)))
