# packages/haywire-core/src/haywire/ui/editor/__init__.py
"""
Editor framework for the Haywire UI system.

Provides BaseEditor, EditorIdentity, the @editor decorator, and EditorRegistry.
The graph canvas implementation lives in haybale_studio.editors.graph_canvas.
"""

from __future__ import annotations

from .base import BaseEditor
from .decorator import editor
from .identity import EditorIdentity, OpenBehavior, SlotName
from .registry import EditorRegistry

__all__ = [
    "EditorIdentity",
    "OpenBehavior",
    "SlotName",
    "BaseEditor",
    "editor",
    "EditorRegistry",
]
