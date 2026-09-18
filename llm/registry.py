"""Provider registry — how the Factory finds a Strategy without any if/else.

Each adapter registers itself under a provider key (a Strategy behind the LLMClient
Protocol). The Factory looks the key up and constructs polymorphically. Adding a
provider = write an adapter + `@register_provider("name")` — the factory never
changes (open/closed principle).
"""

from __future__ import annotations

from collections.abc import Callable

from .ports import LLMClient

# provider key -> a callable that builds an LLMClient given a model name.
# (An adapter class is such a callable: `OllamaClient(model)` returns an instance.)
Builder = Callable[[str], LLMClient]

_PROVIDERS: dict[str, Builder] = {}
_loaded = False


def register_provider(name: str) -> Callable[[Builder], Builder]:
    """Class/function decorator that registers a provider builder under `name`."""

    def decorator(builder: Builder) -> Builder:
        _PROVIDERS[name] = builder
        return builder

    return decorator


def _ensure_adapters_loaded() -> None:
    """Import the adapter package once so every provider self-registers.

    Lazy (function-level) import avoids a circular import: adapters import this
    module at their top, and this runs only after registry is fully loaded.
    """
    global _loaded
    if not _loaded:
        from . import adapters  # noqa: F401  (import for registration side effect)

        _loaded = True


def get_provider_builder(name: str) -> Builder:
    _ensure_adapters_loaded()
    try:
        return _PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown LLM provider {name!r}. Registered: {sorted(_PROVIDERS)}"
        ) from None


def registered_providers() -> list[str]:
    _ensure_adapters_loaded()
    return sorted(_PROVIDERS)
