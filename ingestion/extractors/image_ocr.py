"""
ingestion/extractors/image_ocr.py  —  the IMAGE path (OCR baseline).

For documents with NO text layer — our profiling proved the RAG cheat sheet
(0 chars from pdftotext) and the manga PNG are both images. OCR turns the
picture of text back into text.

This is deliberately the BASELINE, not the final answer. Verified live: OCR
recovered the cheat sheet's "Data Ingestion" page, but with errors
("PDFPLumber", "Confivence"). Those errors are exactly the gap ColPali would
close later — IF the eval numbers prove it's worth ColPali's ~1000x storage
cost. We earn ColPali with a measured number; we don't assume it.

TOOL: tesseract via pytesseract (or the CLI). Renders PDF pages to images with
pdftoppm first, then OCRs each. Language is configurable (eng now; ara needs the
tesseract Arabic language pack installed in the app box for the manga).

WHY OCR before ColPali (matches the roadmap): cheap-and-broad first,
expensive-and-specific last. OCR gives us our FIRST eval numbers on image docs;
without a number we can't justify anything heavier.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from ingestion.extractors.base import Extractor
from ingestion.types import ExtractedDoc, ExtractedPage


class ImageOcrExtractor(Extractor):
    name = "image_ocr"

    def __init__(self, languages: str = "eng", dpi: int = 150) -> None:
        # languages: tesseract lang codes joined by '+', e.g. "eng+ara" for the manga.
        # dpi: render resolution. Higher = better OCR, slower. 150 is a sane default.
        self.languages = languages
        self.dpi = dpi

    def extract(self, path: Path) -> ExtractedDoc:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            pages = self._ocr_pdf(path)
            doc_type = "image_pdf"
        else:  # .png / .jpg / .jpeg — a single image file
            pages = self._ocr_single_image(path)
            doc_type = "image"

        return ExtractedDoc(
            source_filename=path.name,
            doc_type=doc_type,
            extractor_name=f"image_ocr({self.languages})",
            pages=pages,
        )

    def _ocr_pdf(self, path: Path) -> list[ExtractedPage]:
        pages: list[ExtractedPage] = []
        with tempfile.TemporaryDirectory() as tmp:
            prefix = str(Path(tmp) / "page")
            # Render every page to PNG. pdftoppm zero-pads filenames by total pages.
            subprocess.run(
                ["pdftoppm", "-png", "-r", str(self.dpi), str(path), prefix],
                check=True, capture_output=True,
            )
            image_files = sorted(Path(tmp).glob("page*.png"))
            for n, img in enumerate(image_files, start=1):
                text = self._ocr_image_file(img)
                if text.strip():
                    pages.append(ExtractedPage(page_number=n, text=text))
        return pages

    def _ocr_single_image(self, path: Path) -> list[ExtractedPage]:
        text = self._ocr_image_file(path)
        return [ExtractedPage(page_number=1, text=text)] if text.strip() else []

    def _ocr_image_file(self, img: Path) -> str:
        # Use the tesseract CLI (no python binding needed). '-' sends text to stdout.
        result = subprocess.run(
            ["tesseract", str(img), "-", "-l", self.languages],
            capture_output=True, text=True, check=True,
        )
        # Keep non-empty lines; OCR emits lots of blank lines.
        return "\n".join(ln.rstrip() for ln in result.stdout.splitlines() if ln.strip())