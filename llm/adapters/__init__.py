"""Importing this package registers every provider (side effect of the imports).

Each adapter module calls `@register_provider(...)` at import time, so importing
them here populates the registry the Factory reads. Add a new adapter -> add one
import line here; the Factory stays untouched.
"""

from . import anthropic  # noqa: F401  (import for its registration side effect)
from . import ollama  # noqa: F401  (import for its registration side effect)
