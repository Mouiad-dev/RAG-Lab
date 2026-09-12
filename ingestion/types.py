"""
ingestion/types.py  —  the SHARED SHAPES of the ingestion pipeline.

Three plain data containers that every ingestion piece agrees on:

    ExtractedPage  -> one page of text after extraction (number + text)
    ExtractedDoc   -> a whole file after extraction (metadata + list of pages)
    Chunk          -> one retrievable piece of a doc (+ its embedding, filled later)

WHY this file has NO imports from the rest of ingestion: everything else
(extractors, chunkers, service, repository) depends on THESE types, so if this
file imported them back we'd get a circular import. Types sit at the bottom of
the dependency graph and depend on nothing. Keep it that way.

The uniform shape is the whole point of the Strategy pattern here: any extractor
returns an ExtractedDoc, any chunker consumes one and returns list[Chunk], so
you can swap strategies without touching the pieces on either side.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExtractedPage:
    """One page after extraction. page_number is 1-based (matches how humans cite)."""
    page_number: int
    text: str


@dataclass
class ExtractedDoc:
    """A whole file after extraction: the uniform shape every extractor returns.

    doc_type / extractor_name form an audit trail ("which strategy produced this?"),
    which is why the schema stores them — you can later ask "how do OCR'd docs score
    vs text-layer docs?" without re-running ingestion.
    """
    source_filename: str
    doc_type: str                       # text_pdf | image_pdf | image
    extractor_name: str                 # e.g. "text_pdf(docling)" — audit trail
    pages: list[ExtractedPage] = field(default_factory=list)

    @property
    def total_chars(self) -> int:
        """Total non-structural character count across all pages (for logging/summary)."""
        return sum(len(p.text) for p in self.pages)

    @property
    def page_count(self) -> int:
        """How many pages actually yielded text (empty pages are dropped upstream)."""
        return len(self.pages)


@dataclass
class Chunk:
    """One retrievable piece of a document.

    MUTABLE on purpose: the chunker creates it WITHOUT an embedding, then the embed
    step fills `.embedding` in place. The repository refuses to store a chunk whose
    embedding is still None, so a skipped embed step fails loudly instead of writing
    NULL vectors. Every chunk keeps source_filename + page_number so a citation can
    survive all the way to the final grounded answer.
    """
    text: str
    source_filename: str                # citation: which document
    page_number: int                    # citation: which page ("per p.4")
    chunk_index: int                    # position within the document (stable id)
    embedding: list[float] | None = None  # filled by the embed step, before storing
