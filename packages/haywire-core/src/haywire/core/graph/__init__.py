# haywire/core/graph/__init__.py
"""
Graph module - Public API exports.
"""

# Export main classes
from .base import BaseGraph, Variable

# Export types for consumers that need them
from .types import ValidationResult, ChangeReason

# Do NOT export ValidationManager - it's an internal implementation detail

__all__ = [
    "BaseGraph",
    "Variable",
    "ValidationResult",
    "ChangeReason",
]
