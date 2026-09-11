"""
ingestion/service.py  —  the ROUTER + orchestrator (the receptionist).

This is the piece our file-profiling PROVED we need. Three uploads, three
different extraction realities:
    Docker slides   -> real text layer      -> TEXT extractor
    RAG cheat sheet -> 0 chars, image-only  -> IMAGE (OCR) extractor
    manga PNG       -> image file           -> IMAGE (OCR) extractor

The router looks at each document and picks the strategy automatically, using the
exact probe we ran by hand (does pdftotext yield real text?). Then it chunks with
whichever chunker config/rag.yaml selected.

Design:
  - The router is the ONLY place that constructs extractors/chunkers. Everything
    else depends on the abstract types. Add ColPali later = add one branch here +
    one new extractor file; nothing downstream changes. (Open/Closed.)
  - Selection is driven by config, not hardcoded, so the lab can flip strategies.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ingestion.chunkers.base import Chunker
from ingestion.chunkers.naive import NaiveChunker
from ingestion.chunkers.structure_aware import StructureAwareChunker
from ingestion.extractors.base import Extractor
from ingestion.extractors.image_ocr import ImageOcrExtractor
from ingestion.extractors.text_pdf import TextPdfExtractor
from ingestion.types import Chunk, ExtractedDoc

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
# If a PDF yields fewer than this many non-whitespace chars, treat it as image-only.
# Not zero, to tolerate a stray watermark character on an otherwise-scanned page.
TEXT_LAYER_MIN_CHARS = 20


def _pdf_has_text_layer(path: Path) -> bool:
    """The automatic version of the probe we ran live: does this PDF contain
    real, extractable text? Uses pdffonts (any fonts?) + a pdftotext sample."""
    fonts = subprocess.run(
        ["pdffonts", str(path)], capture_output=True, text=True, check=True
    ).stdout.strip().splitlines()
    # pdffonts prints 2 header lines even when empty; >2 lines means fonts exist.
    has_fonts = len(fonts) > 2
    if not has_fonts:
        return False
    sample = subprocess.run(
        ["pdftotext", "-f", "1", "-l", "3", str(path), "-"],
        capture_output=True, text=True, check=True,
    ).stdout
    return len("".join(sample.split())) >= TEXT_LAYER_MIN_CHARS


@dataclass
class IngestionConfig:
    """The slice of config/rag.yaml this service cares about (ingestion.*)."""
    chunker: str = "structure_aware"      # "structure_aware" | "naive"
    chunk_size: int = 800
    chunk_overlap: int = 100
    ocr_languages: str = "eng"            # "eng+ara" once the manga needs Arabic

    @classmethod
    def from_yaml(cls, cfg: dict) -> "IngestionConfig":
        ing = cfg.get("ingestion", {})
        return cls(
            chunker=ing.get("chunker", "structure_aware"),
            chunk_size=ing.get("chunk_size", 800),
            chunk_overlap=ing.get("chunk_overlap", 100),
            ocr_languages=ing.get("ocr_languages", "eng"),
        )


@dataclass
class IngestionResult:
    doc: ExtractedDoc
    chunks: list[Chunk]

    @property
    def summary(self) -> str:
        return (
            f"{self.doc.source_filename}: routed->{self.doc.extractor_name}, "
            f"{len(self.doc.pages)} page(s), {self.doc.total_chars} chars, "
            f"{len(self.chunks)} chunk(s)"
        )


class IngestionService:
    """Profiles a file, routes to the right extractor, then chunks it."""

    def __init__(self, config: IngestionConfig) -> None:
        self.config = config

    # ---- routing: pick the extractor based on what the file ACTUALLY is ------
    def _select_extractor(self, path: Path) -> Extractor:
        suffix = path.suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            return ImageOcrExtractor(languages=self.config.ocr_languages)
        if suffix == ".pdf":
            if _pdf_has_text_layer(path):
                return TextPdfExtractor()
            return ImageOcrExtractor(languages=self.config.ocr_languages)  # image-only PDF
        raise ValueError(f"unsupported file type: {suffix}")

    # ---- chunker selection: driven by config, not hardcoded -----------------
    def _select_chunker(self) -> Chunker:
        if self.config.chunker == "naive":
            return NaiveChunker(self.config.chunk_size, self.config.chunk_overlap)
        if self.config.chunker == "structure_aware":
            return StructureAwareChunker(self.config.chunk_size, self.config.chunk_overlap)
        raise ValueError(f"unknown chunker: {self.config.chunker}")

    # ---- the public entry point ---------------------------------------------
    def ingest(self, path: Path) -> IngestionResult:
        extractor = self._select_extractor(path)
        doc = extractor.extract(path)
        chunker = self._select_chunker()
        chunks = chunker.chunk(doc)
        return IngestionResult(doc=doc, chunks=chunks)

    def embed_chunks(self, chunks: list[Chunk], embedder) -> list[Chunk]:
        """Fill each chunk's .embedding in place using the given Embedder.

        Batched via embed_many so an adapter can optimize the round-trips. The
        embedder itself guards the dimension, so a wrong-size vector raises here,
        not silently at DB insert time.
        """
        vectors = embedder.embed_many([c.text for c in chunks])
        for c, v in zip(chunks, vectors):
            c.embedding = v
        return chunks