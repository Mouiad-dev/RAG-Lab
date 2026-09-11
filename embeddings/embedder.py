"""
embeddings/embedder.py  —  the EMBEDDINGS Port + Adapter.

Turns text into a dense vector ("meaning fingerprint"). Same idea as the LLM
Port/Adapter you locked in Step 5: a thin interface (Port) with one concrete
implementation per provider (Adapter), so we can swap providers without touching
callers. Explicit over implicit; no framework lock-in.

MODEL: BGE-M3 via Ollama (verified 2026): multilingual (100+ langs incl. Arabic),
1024-dim dense vectors, ~1.2GB, $0 local. Perfect for a mixed AR+EN corpus.

🔴 THE GUARD THAT MATTERS: a real, recurring 2026 bug is embedder dim (1024) not
matching the vector DB column (often a hardcoded 1536/768) -> "dimension mismatch
or SILENT FAILURE." We refuse to fail silently: every returned vector is checked
against the configured dimension and raises LOUDLY on mismatch.

RULE (Step 6): the SAME embedder+dimension MUST be used at store-time AND
query-time, or points live on different maps and search returns garbage.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

import httpx


class Embedder(ABC):
    """Port: the contract every embedding provider must satisfy."""

    #: expected output dimension; callers and the DB column rely on this
    dimension: int

    @abstractmethod
    def embed_one(self, text: str) -> list[float]:
        """Embed a single string into a dense vector of length == self.dimension."""
        raise NotImplementedError

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch. Default loops embed_one; adapters may override for speed."""
        return [self.embed_one(t) for t in texts]

    # ---- the loud guard: never let a wrong-size vector through ---------------
    def _check_dim(self, vector: list[float]) -> list[float]:
        if len(vector) != self.dimension:
            raise ValueError(
                f"embedding dimension mismatch: model returned {len(vector)} "
                f"but config expects {self.dimension}. This is the classic silent-"
                f"failure bug — fix embeddings.dimension in rag.yaml OR the model, "
                f"and make sure the pgvector column is vector({self.dimension})."
            )
        return vector


class OllamaEmbedder(Embedder):
    """Adapter: BGE-M3 (or any embedding model) served by a local Ollama box."""

    def __init__(
        self,
        model: str = "bge-m3",
        dimension: int = 1024,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.model = model
        self.dimension = dimension
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434")
        self.timeout = timeout

    def embed_one(self, text: str) -> list[float]:
        # Ollama's embeddings endpoint: POST /api/embeddings {model, prompt}
        resp = httpx.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        vector = resp.json()["embedding"]
        return self._check_dim(vector)

    @classmethod
    def from_yaml(cls, cfg: dict) -> "OllamaEmbedder":
        emb = cfg.get("embeddings", {})
        return cls(
            model=emb.get("provider_model", "bge-m3"),
            dimension=emb.get("dimension", 1024),
        )