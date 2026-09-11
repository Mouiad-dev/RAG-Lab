"""
ingestion/extractors/base.py  —  the EXTRACTOR contract.

An extractor turns a file on disk into an ExtractedDoc (the uniform shape).
That's the ONLY thing every extractor promises. How it does it — Docling, OCR,
ColPali — is its own private business.

This is the Strategy pattern's interface: one method, one return type. The router
(service.py) picks WHICH concrete extractor to call; nothing else in the codebase
constructs an extractor directly, so adding a new one is a local change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ingestion.types import ExtractedDoc


class Extractor(ABC):
    """Abstract base: every extraction strategy is an Extractor."""

    #: short stable name, recorded on ExtractedDoc for the audit trail
    name: str = "base"

    @abstractmethod
    def extract(self, path: Path) -> ExtractedDoc:
        """Turn the file at `path` into the uniform ExtractedDoc shape.

        Implementations MUST:
          - set ExtractedDoc.extractor_name = self.name
          - populate pages with 1-based page_number
          - never raise on 'no text found' — return an ExtractedDoc with empty
            pages instead, so the router can detect the miss and re-route.
        """
        raise NotImplementedError