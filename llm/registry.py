"""LLM provider registry — a thin instance of the generic ProviderRegistry.

Keeps the same public names (`register_provider`, `get_provider_builder`,
`registered_providers`) so adapters keep using `@register_provider("...")`.
"""

from __future__ import annotations

from common.registry import ProviderRegistry

from .ports import LLMClient


def _load_adapters() -> None:
    from . import adapters  # noqa: F401  (import triggers self-registration)


_registry: ProviderRegistry[LLMClient] = ProviderRegistry(
    "LLM provider", loader=_load_adapters
)

register_provider = _registry.register
get_provider_builder = _registry.get
registered_providers = _registry.names
