"""Error handling for Haywire.

Use ``HaywireException.from_exception()`` or ``HaywireException.create()``.
"""

from .haywire_exception import HaywireException, ErrorSeverity

__all__ = [
    "HaywireException",
    "ErrorSeverity",
]
