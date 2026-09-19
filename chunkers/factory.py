"""Factory — reads config, looks up the chunker strategy in the registry. No if/else.

Unlike the LLM/embedder factories (which pass a `model`), a chunker is configured by
tuning params (e.g. chunk_size, overlap). We pass those straight through as kwargs, so
each strategy owns its own knobs and defaults.
"""

from __future__ import annotations

import os

from .ports import Chunker
from .registry import get_chunker_builder


def build_chunker(*, strategy: str | None = None, **params) -> Chunker:
    strategy = strategy or os.environ.get("CHUNKER", "fixed_size")
    builder = get_chunker_builder(strategy)  # polymorphic lookup
    return builder(**params)
