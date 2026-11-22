"""Re-exports the Haywire exception API (:class:`HaywireException`, :class:`ErrorSeverity`)."""

from __future__ import annotations

from .haywire_exception import ErrorSeverity, HaywireException

__all__ = ["HaywireException", "ErrorSeverity"]
