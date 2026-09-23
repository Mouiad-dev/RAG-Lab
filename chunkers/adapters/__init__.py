"""Importing this package registers every chunker (import side effect)."""

from . import fixed_size  # noqa: F401  (import for its registration side effect)
from . import recursive  # noqa: F401
from . import sentence  # noqa: F401
from . import semantic  # noqa: F401
from . import document  # noqa: F401
from . import token_aware  # noqa: F401
from . import agentic  # noqa: F401
