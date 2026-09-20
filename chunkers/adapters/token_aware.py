"""Token-Aware chunker (#7) — size measured in REAL tokens, not characters.

Fixed-Size's honest analog in the token domain: slide a window of `chunk_tokens` real
tokens with `overlap_tokens` overlap. Because it measures the model's actual token budget,
a chunk fits the embedder/LLM limit on BOTH languages — where a char window would blow the
budget on Arabic. This is also the step where `ChunkData.token_count` finally carries a
REAL number instead of None.

Like the semantic chunker (which needs an embedder), this needs a tokenizer — injected as a
constructor dependency, so the `Chunker` Port signature stays `chunk(text)`. Windowing over
the token-id list is a pure function (`window_ids`), unit-tested without downloading a model.
"""

from __future__ import annotations

from ..ports import ChunkData
from ..registry import register_chunker

DEFAULT_CHUNK_TOKENS = 256
DEFAULT_OVERLAP_TOKENS = 32


def window_ids(ids: list, chunk_tokens: int, overlap_tokens: int) -> list[list]:
    """Slide a fixed token window with overlap. Pure function → unit-tested with plain lists."""
    if not ids:
        return []
    step = chunk_tokens - overlap_tokens
    windows: list[list] = []
    start = 0
    while start < len(ids):
        windows.append(ids[start : start + chunk_tokens])
        if start + chunk_tokens >= len(ids):
            break  # this window already reached the end; no redundant tail
        start += step
    return windows


@register_chunker("token")
class TokenAwareChunker:
    strategy = "token"

    def __init__(
        self,
        *,
        chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
        tokenizer=None,
    ):
        if chunk_tokens <= 0:
            raise ValueError("chunk_tokens must be positive")
        if not 0 <= overlap_tokens < chunk_tokens:
            raise ValueError("overlap_tokens must be >= 0 and < chunk_tokens")
        self.chunk_tokens = chunk_tokens
        self.overlap_tokens = overlap_tokens
        self._tokenizer = tokenizer

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            from ..tokenization import build_tokenizer

            self._tokenizer = build_tokenizer()
        return self._tokenizer

    def chunk(self, text: str) -> list[ChunkData]:
        text = text.strip()
        if not text:
            return []

        ids = self.tokenizer.encode(text)
        windows = window_ids(ids, self.chunk_tokens, self.overlap_tokens)

        result: list[ChunkData] = []
        for window in windows:
            piece = self.tokenizer.decode(window).strip()
            if not piece:
                continue
            result.append(
                ChunkData(
                    text=piece,
                    ordinal=len(result),
                    token_count=len(window),  # REAL token count, at last
                    metadata={
                        "strategy": self.strategy,
                        "chunk_tokens": self.chunk_tokens,
                        "overlap_tokens": self.overlap_tokens,
                    },
                )
            )
        return result
