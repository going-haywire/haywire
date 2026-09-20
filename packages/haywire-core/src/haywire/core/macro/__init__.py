"""Macros: Subgraphs that live in their own file and are placed like nodes."""

from .registry import MacroRegistry
from .source import is_macro_key, is_macro_placement, macro_edit_refusal, macro_source_path
from .template import MacroTemplate

__all__ = [
    "MacroRegistry",
    "MacroTemplate",
    "is_macro_key",
    "is_macro_placement",
    "macro_edit_refusal",
    "macro_source_path",
]
