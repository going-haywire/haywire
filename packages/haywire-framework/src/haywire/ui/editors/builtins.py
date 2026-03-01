# packages/haywire-framework/src/haywire/ui/editors/builtins.py
"""
Bootstrap function for registering built-in framework editors.

Called from the DI provider in HaywireModule to register framework-provided
editors. App-level editors (e.g., LibraryBrowser) are NOT registered here —
they are registered directly in app.py after injector creation.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.ui.editor.registry import EditorTypeRegistry


def register_builtin_editors(registry: 'EditorTypeRegistry') -> None:
    """Register all built-in framework editors into the registry.

    Args:
        registry: The EditorTypeRegistry DI singleton to register into.
    """
    from haywire.ui.editors.graph_editor import GraphEditor
    registry._register_class(GraphEditor, library_identity=None)

    from haywire.ui.editors.properties_editor import PropertiesEditor
    registry._register_class(PropertiesEditor, library_identity=None)

    from haywire.ui.editors.console_editor import ConsoleEditor
    registry._register_class(ConsoleEditor, library_identity=None)
