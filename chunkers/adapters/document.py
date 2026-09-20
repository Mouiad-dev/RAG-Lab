"""Document-Based / structure-aware chunker (#6) — split on the doc's OWN structure.

For a Markdown-structured doc, each heading (#, ##, ###...) starts a section, and the
section stays intact as a chunk. The heading path (breadcrumb like
["Refund Policy", "Eligibility"]) rides in metadata — a far better citation than a raw
offset. The plan's "v1 winner": policies/contracts/manuals ARE heading-structured, and a
human cites the section.

Two design choices:
- COMPOSITION: an oversized section is delegated to a `body_chunker` (default recursive),
  keeping this chunker focused on structure and reusing proven size-splitting. The
  `Chunker` Port stays chunk(text); the body chunker is an injected dependency.
- FALLBACK: a doc with NO headings delegates entirely to the fallback chunker (this
  strategy only makes sense on structured text; don't emit one giant chunk).

NOTE(extraction): this reads Markdown ATX headings from text. Extracting structure from
real PDFs (Unstructured / LlamaParse) is the deferred Phase-2 OCR router + post-project
tool pass; this same chunker will consume whatever headings that yields.
"""

from __future__ import annotations

import re

from ..ports import ChunkData
from ..registry import register_chunker

DEFAULT_CHUNK_SIZE = 1000

# ATX Markdown heading: 1-6 '#', a space, then the title. Setext (=== / ---) not handled.
_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def parse_sections(text: str) -> list[tuple[list[str], str]]:
    """Parse Markdown into (heading_path, section_text) pairs. Pure function → unit-tested.

    A section is a heading line plus its body up to the next heading. Text before the
    first heading is a preamble with an empty heading_path. `heading_path` is the stack of
    ancestor headings by level (e.g. under "## Eligibility" inside "# Refund Policy" →
    ["Refund Policy", "Eligibility"]).
    """
    sections: list[tuple[list[str], str]] = []
    stack: list[tuple[int, str]] = []  # (level, title) ancestors of the current section
    current_lines: list[str] = []
    current_path: list[str] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append((list(current_path), body))

    for line in text.splitlines():
        m = _HEADING.match(line)
        if not m:
            current_lines.append(line)
            continue
        # a heading starts a new section: flush the previous one first
        flush()
        level = len(m.group(1))
        title = m.group(2).strip()
        # pop deeper-or-equal levels off the stack, then push this heading
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        current_path = [t for _, t in stack]
        current_lines = [line]  # keep the heading line in the section text
    flush()
    return sections


@register_chunker("document")
class DocumentChunker:
    strategy = "document"

    def __init__(self, *, chunk_size: int = DEFAULT_CHUNK_SIZE, body_chunker=None):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self.chunk_size = chunk_size
        self._body_chunker = body_chunker  # lazily built (avoids import-time cost)

    @property
    def body_chunker(self):
        if self._body_chunker is None:
            from ..factory import build_chunker

            self._body_chunker = build_chunker(
                strategy="recursive", chunk_size=self.chunk_size, overlap=0
            )
        return self._body_chunker

    def chunk(self, text: str) -> list[ChunkData]:
        text = text.strip()
        if not text:
            return []

        sections = parse_sections(text)
        # No headings at all -> this strategy doesn't apply; delegate wholesale.
        if not sections or (len(sections) == 1 and not sections[0][0]):
            return self._delegate_whole(text)

        result: list[ChunkData] = []
        for heading_path, body in sections:
            pieces = (
                [body]
                if len(body) <= self.chunk_size
                else [p.text for p in self.body_chunker.chunk(body)]  # oversized -> sub-split
            )
            for piece in pieces:
                piece = piece.strip()
                if not piece:
                    continue
                result.append(
                    ChunkData(
                        text=piece,
                        ordinal=len(result),
                        metadata={
                            "strategy": self.strategy,
                            "heading_path": heading_path,
                            "chunk_size": self.chunk_size,
                        },
                    )
                )
        return result

    def _delegate_whole(self, text: str) -> list[ChunkData]:
        """No headings: reuse the fallback chunker but stamp our own strategy + empty path."""
        return [
            ChunkData(
                text=p.text,
                ordinal=i,
                metadata={
                    "strategy": self.strategy,
                    "heading_path": [],
                    "chunk_size": self.chunk_size,
                    "fallback": "recursive",
                },
            )
            for i, p in enumerate(self.body_chunker.chunk(text))
        ]
