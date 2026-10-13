"""Macros: Subgraphs that live in their own file and are placed like nodes."""

from .registry import MacroRegistry
from .source import (
    count_placements,
    is_macro_key,
    is_macro_placement,
    macro_edit_refusal,
    macro_source_path,
    macro_template,
    origin_label,
)
from .template import MacroTemplate

__all__ = [
    "MacroRegistry",
    "MacroTemplate",
    "count_placements",
    "is_macro_key",
    "is_macro_placement",
    "macro_edit_refusal",
    "macro_source_path",
    "macro_template",
    "origin_label",
]
