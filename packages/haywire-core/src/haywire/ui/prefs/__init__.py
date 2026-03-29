# haywire/ui/prefs/__init__.py
"""
Framework preference singletons — Settings + setting() subclasses for the
old haybale-studio FrameworkSettings classes.

All classes configure UI behaviour (canvas, edges, nodes, minimap, editor
interaction) and are consumed by framework renderers and editors.

Registered as DI singletons in HaywireModule.  Panels access them via:

    instance = context.app.injector.get(ExecutionSettings)
    render_reactive(instance)
"""

from .debug import DebugSettings
from .editor import EditorSettings
from .execution import ExecutionSettings
from .canvas import CanvasSettings
from .edge_ui import EdgeUISettings
from .minimap import MinimapSettings

__all__ = [
    "DebugSettings",
    "EditorSettings",
    "ExecutionSettings",
    "CanvasSettings",
    "EdgeUISettings",
    "MinimapSettings",
]
