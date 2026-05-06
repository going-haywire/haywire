"""
ConnectionInfoPopup - Detailed connection information display component

This component provides a dedicated popup for inspecting edge/connection details including:
- Connection path (nodes and ports)
- Validation status
- Error details with full error rendering
- Warning messages
- Adapter chain visualization and testing
- Execution statistics
"""

from nicegui import ui
from typing import Optional

from haywire.core.edge.edge import Edge
from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.edge.edge_wrapper import EdgeWrapperState

from haywire.ui import elements as hui
from haywire.ui.errors.error_info import error_render_detail

from haywire.ui.components.popup import Popup


class EdgeInfoPopup:
    """Dedicated popup for displaying detailed connection/edge information."""

    def __init__(self):
        self._info_popup: Optional[Popup] = None

    def show(self, x: float, y: float, edge_id: str, edge: Edge, state: EdgeWrapperState):
        """Show detailed connection information in a dedicated popup."""
        # Close any existing popup first
        self.close()

        # Create a larger popup for detailed information
        popup = Popup.create_context_menu(
            "Connection Details", x + 10, y + 10, width="400px", clamp_to_viewport=False
        )

        with popup:
            with ui.column().classes("w-full gap-2 p-2"):
                # Header with connection status
                with ui.row().classes("w-full"):
                    ui.label(f"{edge.edge_type}").classes("text-xs hw-text-muted ml-2 mt-2")
                    is_valid = state.is_valid()
                    status_icon = "✓" if is_valid else "✗"
                    status_color = "hw-text-success" if is_valid else "hw-text-danger"
                    status_text = "Valid" if is_valid else "Invalid"
                    ui.label(f"{status_icon} {status_text}").classes(f"text-sm font-bold {status_color}")

                ui.separator().classes("my-2")

                # Error Section (if present, expandable, default open)
                error = state.get_error()
                if error and isinstance(error, HaywireException):
                    with hui.expansion_section("Error Details"):
                        with (
                            ui.card()
                            .classes("w-full p-3")
                            .style("background: var(--hw-danger-bg); border: 1px solid var(--hw-danger);")
                        ):
                            ui.label(f"Category: {error.category}").classes("text-xs hw-text-danger ml-2")
                            # Render the error detail with button to show full details
                            error_render_detail(error)

                # Warning Section (if present, expandable, default open)
                if state.has_warning():
                    with hui.expansion_section("Warning"):
                        with (
                            ui.card()
                            .classes("w-full p-3")
                            .style("background: var(--hw-bg-surface); border: 1px solid var(--hw-border);")
                        ):
                            with ui.column():
                                for warning in state.warnings:
                                    ui.label(f"⚠ {warning}").classes("text-xs hw-text-warning ml-2")

                # Adapter Chain Section (if available, expandable, default closed)
                if edge.chain_adapter_keys:
                    with hui.expansion_section("Adapter Chain", default_open=False):
                        with (
                            ui.card()
                            .classes("w-full p-3")
                            .style("background: var(--hw-bg-surface); border: 1px solid var(--hw-border);")
                        ):
                            # Display each adapter in the chain
                            for i, adapter_key in enumerate(edge.chain_adapter_keys, 1):
                                ui.label(f"{i}. {adapter_key}").classes("text-xs hw-text-accent ml-2")

                if state.execution_count > 0:
                    # Execution Statistics Section (expandable, default closed)
                    with hui.expansion_section("Execution Statistics", default_open=False):
                        exec_count = state.execution_count
                        ui.label(f"Execution Count: {exec_count}").classes("text-xs hw-text-muted ml-2")

                        avg_time = state.average_execution_time_us
                        if avg_time > 0:
                            ui.label(f"Average Time: {avg_time:.1f} μs").classes(
                                "text-xs hw-text-muted ml-2"
                            )
                        else:
                            ui.label("Average Time: Not measured").classes("text-xs hw-text-dim ml-2")

                        ui.label(f"Tested value: {state.example_test_value}").classes(
                            "text-xs hw-text-muted ml-2"
                        )
                        ui.label(f"Tested result: {state.example_test_result}").classes(
                            "text-xs hw-text-muted ml-2"
                        )

                # Connection Path Section (Expandable, default closed)
                with hui.expansion_section("Connection Path", default_open=False):
                    ui.label("Connection Path").classes("font-semibold text-sm")
                    ui.label(f"{edge.source_node_id} [{edge.outlet_port_id}]").classes("text-xs opacity-70")
                    ui.label("↓").classes("text-xs opacity-50 ml-2")
                    ui.label(f"{edge.sink_node_id} [{edge.inlet_port_id}]").classes("text-xs opacity-70")

                # Close button
                ui.separator().classes("my-2")
                btn_close = ui.button("Close", on_click=lambda: self.close())
                btn_close.props("flat")
                btn_close.classes("w-full text-sm py-2")

        popup.open()
        self._info_popup = popup

    def close(self):
        """Close the connection info popup."""
        if self._info_popup:
            self._info_popup.close()
            self._info_popup.delete()
            self._info_popup = None
