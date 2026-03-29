# packages/haywire-core/src/haywire/ui/panels/node_settings_panel.py
"""
NodeSettingsPanel — displays node validation state and lifecycle status.
"""

from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout

if False:  # TYPE_CHECKING
    from haywire.ui.context import SessionContext


@panel(
    registry_id="node_settings",
    editor="properties",
    scope="node",
    label="Status",
    icon="check_circle",
    order=30,
    default_open=False,
)
class NodeStatusPanel(BasePanel):
    """Displays the validation and lifecycle status of the selected node."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_node is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        node = context.active_node
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
