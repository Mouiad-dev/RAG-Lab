"""Importing this package registers every embedder (import side effect)."""

from . import ollama  # noqa: F401  (import for its registration side effect)
