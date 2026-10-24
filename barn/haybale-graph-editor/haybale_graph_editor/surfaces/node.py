"""Inspector surfaces for the active node: identity/introspection, and settings.

Neither declares ``provides`` — inspector panels read state and need no host
verbs, so the properties editor passes them no host at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.surface import Presentation, Surface

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


class NodeInspector(Surface):
    """Properties tab describing the active node."""

    id = "node"
    order = 60
    presentation = Presentation(label="Node", icon=hui.icon.node)

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        return ctx.data[EditState].active_node is not None


class SettingsInspector(Surface):
    """Properties tab for the active node's settings."""

    id = "settings"
    order = 65
    presentation = Presentation(label="Settings", icon=hui.icon.node_settings)

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        return ctx.data[EditState].active_node is not None
