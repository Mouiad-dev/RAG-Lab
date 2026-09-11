"""
ingestion/extractors/text_pdf.py  —  the TEXT path.

For PDFs that have a real text layer (our profiling proved the Docker slides do:
3,546 chars extracted). This is the fast, cheap, accurate happy path.

PRIMARY: Docling. It returns structure-aware MARKDOWN — headings as '#', tables
as '|...|' — which the structure_aware chunker later splits on natural seams
instead of blind character counts. Docling is the production choice.

FALLBACK: poppler's `pdftotext -layout`. Docling pulls in torch + CUDA (multi-GB),
so it may not be installed everywhere. Rather than make the pipeline un-runnable
without it, we degrade gracefully to pdftotext, which every poppler install has.
The fallback loses some structure (no markdown table markers) but still produces
usable per-page text — enough to run the whole loop end-to-end.

WHY a fallback at all (senior reasoning): a pipeline that only works when a heavy
optional dependency is present is fragile. Explicit degradation > silent failure.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ingestion.extractors.base import Extractor
from ingestion.types import ExtractedDoc, ExtractedPage


def _docling_available() -> bool:
    try:
        import docling  # noqa: F401
        return True
    except Exception:
        return False


class TextPdfExtractor(Extractor):
    name = "text_pdf"

    def extract(self, path: Path) -> ExtractedDoc:
        if _docling_available():
            pages = self._extract_docling(path)
            used = "text_pdf(docling)"
        else:
            pages = self._extract_pdftotext(path)
            used = "text_pdf(pdftotext-fallback)"

        return ExtractedDoc(
            source_filename=path.name,
            doc_type="text_pdf",
            extractor_name=used,
            pages=pages,
        )

    # ---- primary: Docling (structure-aware markdown) -------------------------
    def _extract_docling(self, path: Path) -> list[ExtractedPage]:
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(str(path))
        # Docling gives us one unified markdown document. We keep it as a single
        # "page 1" block here for simplicity; page-level splitting can be added
        # once we wire Docling's page provenance. The markdown structure (headings,
        # table pipes) is preserved, which is what the structure_aware chunker needs.
        markdown = result.document.export_to_markdown()
        return [ExtractedPage(page_number=1, text=markdown)]

    # ---- fallback: poppler pdftotext, page by page --------------------------
    def _extract_pdftotext(self, path: Path) -> list[ExtractedPage]:
        # First find the page count via pdfinfo.
        info = subprocess.run(
            ["pdfinfo", str(path)], capture_output=True, text=True, check=True
        ).stdout
        page_count = 1
        for line in info.splitlines():
            if line.startswith("Pages:"):
                page_count = int(line.split(":")[1].strip())
                break

        pages: list[ExtractedPage] = []
        for n in range(1, page_count + 1):
            # -layout preserves spatial columns (important for the 2-col slides).
            out = subprocess.run(
                ["pdftotext", "-layout", "-f", str(n), "-l", str(n), str(path), "-"],
                capture_output=True, text=True, check=True,
            ).stdout
            # Collapse the runs of blank lines pdftotext emits, keep real breaks.
            cleaned = "\n".join(
                ln.rstrip() for ln in out.splitlines() if ln.strip()
            )
            if cleaned:
                pages.append(ExtractedPage(page_number=n, text=cleaned))
        return pages