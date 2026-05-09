# packages/haywire-core/src/haywire/ui/panels/node_settings_panel.py
"""
NodeSettingsPanel — displays node validation state and lifecycle status.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel

from haybale_studio.focuses import NodeFocus
from haybale_studio.editors.properties_editor_actions import PropertiesEditorActions
from haybale_studio.state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    action=PropertiesEditorActions,
    focus=NodeFocus,
    label="Status",
    icon=hui.icon.node_status,
    order=30,
    default_open=False,
)
class NodeStatusPanel(BasePanel):
    """Displays the validation and lifecycle status of the selected node."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node.value is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: PropertiesEditorActions,
    ) -> None:
        node = ctx.data[EditState].active_node.value
        if node is None:
            return
        try:
            wrapper_state = getattr(node, "state", None)
            if wrapper_state is None:
                layout.label("No state available")
                return

            _is_valid_fn = getattr(wrapper_state, "is_valid", None)
            is_valid = wrapper_state.is_valid() if callable(_is_valid_fn) else "?"
            layout.label(f"Valid: {is_valid}")
            layout.label(f"Registered: {getattr(wrapper_state, 'is_registered', '?')}")
            layout.label(f"Initialized: {getattr(wrapper_state, 'is_initialized', '?')}")
            layout.label(f"Structural: {getattr(wrapper_state, 'is_structural', '?')}")
            layout.label(f"Tested: {getattr(wrapper_state, 'has_test_passed', '?')}")

            _get_errors_fn = getattr(wrapper_state, "get_errors", None)
            errors = wrapper_state.get_errors() if callable(_get_errors_fn) else None
            if errors:
                layout.separator()
                layout.label("Errors:")
                for err in errors:
                    layout.label(f"  ! {err}")

        except Exception:
            layout.label("Error reading status")
