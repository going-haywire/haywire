# haywire/core/settings/builtins/__init__.py
"""
Framework-level built-in settings.

Only NodeInstanceSettings lives here — it is injected into every node by the
framework itself and must be available before any library is loaded.

All other settings (ui.node, ui.edge, ui.canvas, ui.minimap, execution,
debug, editor, workbench, node theme) are registered by haybale-studio.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import GlobalSettingsRegistry

from .node_instance import NodeInstanceSettings  # noqa: F401 — re-exported for callers


def register_all(registry: 'GlobalSettingsRegistry') -> None:
    """Register framework-level built-in settings (NodeInstanceSettings only)."""
    registry.register_schema(NodeInstanceSettings)
