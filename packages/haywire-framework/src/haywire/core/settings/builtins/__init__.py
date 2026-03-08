# haywire/core/settings/builtins/__init__.py
"""
Built-in settings definitions (schema-based GlobalSettings classes).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import GlobalSettingsRegistry

# Import all builtin modules to ensure schema classes are defined
from .ui_node import NodeUISettings
from .ui_edge import EdgeUISettings
from .ui_canvas import CanvasUISettings
from .ui_minimap import MinimapUISettings
from .execution import ExecutionSettings
from .debug import DebugSettings
from .editor import EditorSettings
from .workbench import WorkbenchSettings, NodeThemeSettings
from .node_instance import NodeInstanceSettings  # noqa: F401 — re-exported for callers

# All GlobalSettings schema classes (for explicit registration)
BUILTIN_SCHEMA_CLASSES = [
    NodeUISettings,
    EdgeUISettings,
    CanvasUISettings,
    MinimapUISettings,
    ExecutionSettings,
    DebugSettings,
    EditorSettings,
    WorkbenchSettings,
    NodeThemeSettings,
]


def register_all(registry: 'GlobalSettingsRegistry') -> None:
    """
    Register all built-in global settings schema classes.

    Args:
        registry: The global settings registry
    """
    for cls in BUILTIN_SCHEMA_CLASSES:
        registry.register_schema(cls)
