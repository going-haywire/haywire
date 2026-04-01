# haywire/ui/prefs/__init__.py
"""
Framework preference singletons — Settings + field() subclasses for the
old haybale-studio FrameworkSettings classes.

All classes configure UI behaviour (canvas, edges, nodes, minimap, editor
interaction) and are consumed by framework renderers and editors.

Registered as DI singletons in HaywireModule.  Panels access them via:

    instance = context.app.injector.get(ExecutionSettings)
    render_reactive(instance)
"""

from .editor import EditorSettings
from .canvas import CanvasSettings
from .edge_ui import EdgeUISettings

__all__ = [
    "EditorSettings",
    "CanvasSettings",
    "EdgeUISettings",
]
