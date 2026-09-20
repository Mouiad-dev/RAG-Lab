"""The real tokenizer — bge-m3's own BPE, so token counts match the embedder's budget.

Why a real tokenizer (and not chars÷4): characters ≠ tokens, and the gap is language-
dependent — Arabic costs ~3× the tokens per character vs English (the "Arabic tax"). A
char-based chunk can silently blow a token budget on AR text. Counting real tokens is the
only honest way to respect the model's context limit — a hand-rolled approximation would
be exactly the kind of fake we forbid.

We use the lightweight `tokenizers` runtime (Rust, no torch) and load bge-m3's exact
`tokenizer.json` from the Hub via `huggingface_hub` (downloaded once, cached in the
`hf_cache` Docker volume). This is a foundational primitive (Track Phase 0), the same
category as pgvector / Ollama / the embedder — not a RAG framework.
"""

from __future__ import annotations

import os
from functools import lru_cache

DEFAULT_TOKENIZER_MODEL = "BAAI/bge-m3"  # matches our embedder → exact budget


class HFTokenizer:
    """Thin wrapper over a `tokenizers.Tokenizer`. Encodes CONTENT tokens (no BOS/EOS)."""

    def __init__(self, model: str | None = None):
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        self.model = model or os.environ.get("TOKENIZER_MODEL", DEFAULT_TOKENIZER_MODEL)
        path = hf_hub_download(repo_id=self.model, filename="tokenizer.json")
        self._tok = Tokenizer.from_file(path)

    def encode(self, text: str) -> list[int]:
        return self._tok.encode(text, add_special_tokens=False).ids

    def decode(self, ids: list[int]) -> str:
        return self._tok.decode(ids, skip_special_tokens=True)

    def count(self, text: str) -> int:
        return len(self.encode(text))


@lru_cache(maxsize=4)
def build_tokenizer(model: str | None = None) -> HFTokenizer:
    """Cached: load the tokenizer once per process (the file read + parse isn't free)."""
    return HFTokenizer(model)
