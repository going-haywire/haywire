# haywire/core/graph/__init__.py
"""Public API of the graph package.

``ValidationManager`` is internal; reach validation through ``BaseGraph``.
"""

from __future__ import annotations

from .base import BaseGraph, Variable

from .types import ValidationResult, ChangeReason

__all__ = [
    "BaseGraph",
    "Variable",
    "ValidationResult",
    "ChangeReason",
]
