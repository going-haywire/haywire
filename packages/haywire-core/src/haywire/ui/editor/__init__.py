# packages/haywire-core/src/haywire/ui/editor/__init__.py
"""
Editor framework for the Haywire UI system.

Provides BaseEditor, EditorIdentity, the @editor decorator, and EditorTypeRegistry.
The graph canvas implementation lives in haywire.ui.graph_canvas.
"""

from .identity import EditorIdentity
from .base import BaseEditor
from .decorator import editor
from .registry import EditorTypeRegistry

__all__ = [
    'EditorIdentity',
    'BaseEditor',
    'editor',
    'EditorTypeRegistry',
]
