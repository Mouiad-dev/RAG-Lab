"""Embedder registry — another instance of the generic ProviderRegistry."""

from __future__ import annotations

from common.registry import ProviderRegistry

from .ports import Embedder


def _load_adapters() -> None:
    from . import adapters  # noqa: F401  (import triggers self-registration)


_registry: ProviderRegistry[Embedder] = ProviderRegistry(
    "embedder provider", loader=_load_adapters
)

register_embedder = _registry.register
get_embedder_builder = _registry.get
registered_embedders = _registry.names
