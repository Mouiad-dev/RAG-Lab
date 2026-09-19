"""The extract stage: turn a stored file's bytes into plain text.

Step 2.1 handles the text path only — plain-text and markdown files decoded as
UTF-8. That's enough to exercise the full extract -> chunk -> embed -> store line
end to end and keep the Pipeline shape honest.

NOTE(router, deferred): the real ingestion router — text-PDF vs image -> OCR — bolts
onto THIS stage later in Phase 2. `extract_text` is the single seam it slots into:
add a branch that dispatches on content type to a PDF/OCR extractor. Nothing upstream
or downstream changes.
"""

from __future__ import annotations

from .models import Document

# Content types / extensions we can decode as text today.
#TODO: to expose those to be controlled by the admin later
_TEXT_CONTENT_TYPES = {"text/plain", "text/markdown", "text/x-markdown", ""}
_TEXT_SUFFIXES = (".txt", ".md", ".markdown", ".text")


class UnsupportedContentError(Exception):
    """Raised when the file isn't something the current extractor can read."""


def _looks_like_text(document: Document) -> bool:
    name = (document.original_filename or document.file.name or "").lower()
    if name.endswith(_TEXT_SUFFIXES):
        return True
    return document.content_type in _TEXT_CONTENT_TYPES


def extract_text(document: Document) -> str:
    """Read the document's file and return its text.

    Raises UnsupportedContentError for anything the text path can't handle yet
    (e.g. a PDF or image) — a clear signal that the OCR/PDF branch is the next seam.
    """
    if not _looks_like_text(document):
        raise UnsupportedContentError(
            f"No text extractor for content_type={document.content_type!r} / "
            f"file={document.original_filename!r}. "
            "PDF/image (OCR) extraction is a later Phase-2 step."
        )

    document.file.open("rb")
    try:
        raw = document.file.read()
    finally:
        document.file.close()

    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return raw
