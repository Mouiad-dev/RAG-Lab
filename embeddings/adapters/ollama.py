"""Ollama embedder — real embeddings from BGE-M3 ($0, multilingual AR+EN).

BGE-M3 outputs 1024-dim vectors — must equal documents.models.EMBEDDING_DIM (the
Chunk.vector column size). No Ollama dict escapes this file.
"""

from __future__ import annotations

import os

import httpx

from ..registry import register_embedder

# BGE-M3 is 1024-dim. Keep in lockstep with documents.models.EMBEDDING_DIM.
DEFAULT_MODEL = "bge-m3"
BGE_M3_DIM = 1024


@register_embedder("ollama")
class OllamaEmbedder:
    provider = "ollama"

    def __init__(self, model: str | None = None, *, base_url: str | None = None, timeout: float = 60.0):
        self.model = model or DEFAULT_MODEL
        self.dimensions = BGE_M3_DIM
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")).rstrip("/")
        self.timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = httpx.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": texts},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]
