# haywire/ui/prefs/__init__.py
"""
Framework preference singletons — Reactive + prop() replacements for the
old haybale-studio GlobalSettings classes.

All classes configure UI behaviour (canvas, edges, nodes, minimap, editor
interaction) and are consumed by framework renderers and editors.

Registered as DI singletons in HaywireModule.  Panels access them via:

    instance = context.app.injector.get(ExecutionSettings)
    render_reactive(instance)
"""

from .debug import DebugSettings
from .editor import EditorSettings
from .execution import ExecutionSettings
from .workbench import WorkbenchSettings, NodeThemeSettings
from .canvas import CanvasSettings
from .node_ui import NodeUISettings
from .edge_ui import EdgeUISettings
from .minimap import MinimapSettings

__all__ = [
    'DebugSettings',
    'EditorSettings',
    'ExecutionSettings',
    'WorkbenchSettings',
    'NodeThemeSettings',
    'CanvasSettings',
    'NodeUISettings',
    'EdgeUISettings',
    'MinimapSettings',
]
