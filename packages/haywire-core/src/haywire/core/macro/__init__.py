"""Macros: Subgraphs that live in their own file and are placed like nodes."""

from .registry import MacroRegistry
from .template import MacroTemplate

__all__ = ["MacroRegistry", "MacroTemplate"]
