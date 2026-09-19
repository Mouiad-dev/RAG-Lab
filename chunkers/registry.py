"""Chunker registry — another instance of the generic ProviderRegistry.

Same engine as llm/ and embeddings/. Adding a chunker = a new adapter + one
`@register_chunker("name")` + one import line in adapters/__init__.py. The factory
never changes (open/closed).
"""

from __future__ import annotations

from common.registry import ProviderRegistry

from .ports import Chunker


def _load_adapters() -> None:
    from . import adapters  # noqa: F401  (import triggers self-registration)


_registry: ProviderRegistry[Chunker] = ProviderRegistry(
    "chunker strategy", loader=_load_adapters
)

register_chunker = _registry.register
get_chunker_builder = _registry.get
registered_chunkers = _registry.names
