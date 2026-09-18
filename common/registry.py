"""A generic provider registry — the reusable engine behind every "flip a switch".

One class powers provider/strategy selection for the LLM, the embedder, and later
the chunkers, retrievers, and RAG architectures. Each registry maps a name -> a
builder (an adapter class is a builder: `Cls(model)` -> instance). The Factory looks
the name up and constructs polymorphically — no if/else, open for extension.

`loader` is an optional callable that imports the adapter modules so they self-register
(their `@registry.register(...)` runs on import). It runs once, lazily, on first lookup.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")
Builder = Callable[..., T]


class ProviderRegistry(Generic[T]):
    def __init__(self, kind: str, *, loader: Callable[[], None] | None = None):
        self._kind = kind                       # human label for error messages
        self._loader = loader
        self._providers: dict[str, Builder[T]] = {}
        self._loaded = False

    def register(self, name: str) -> Callable[[Builder[T]], Builder[T]]:
        """Decorator: register a builder under `name`."""

        def decorator(builder: Builder[T]) -> Builder[T]:
            self._providers[name] = builder
            return builder

        return decorator

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self._loaded = True  # set first so the loader's imports can't recurse
            if self._loader is not None:
                self._loader()

    def get(self, name: str) -> Builder[T]:
        self._ensure_loaded()
        try:
            return self._providers[name]
        except KeyError:
            raise ValueError(
                f"Unknown {self._kind} {name!r}. Registered: {sorted(self._providers)}"
            ) from None

    def names(self) -> list[str]:
        self._ensure_loaded()
        return sorted(self._providers)
