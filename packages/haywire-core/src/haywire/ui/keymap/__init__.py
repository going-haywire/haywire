"""Keyboard shortcuts: per-editor keymaps derived from ``EditorCommand`` subscriptions.

See ``build_keymap`` for how combos are claimed and ``report_keymap_problems``
for how unbindable declarations are reported.
"""

from .keymap import Keymap, KeymapClash, KeymapEntry, build_keymap, report_keymap_problems

__all__ = [
    "Keymap",
    "KeymapClash",
    "KeymapEntry",
    "build_keymap",
    "report_keymap_problems",
]
