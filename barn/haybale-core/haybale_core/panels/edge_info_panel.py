# packages/haywire-core/src/haywire/ui/panels/edge_info_panel.py
"""
EdgeInfoPanel — shows source and target information for the selected edge.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from haywire.core.errors.haywire_exception import HaywireException
from haywire.ui.errors.error_info import error_render_detail
from nicegui import ui

from haywire.ui.panel.decorator import panel
from haywire.ui.panel.base import BasePanel, PanelLayout

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext


@panel(
    registry_id="edge_info",
    editors=["properties","context_menu"],
    scopes="edge",
    label="Edge Info",
    icon="linear_scale",
    order=10,
)
class EdgeInfoPanel(BasePanel):
    """Displays source/target node and port info for the selected edge."""

    @classmethod
    def poll(cls, context: "SessionContext") -> bool:
        return context.active_edge is not None

    def draw(self, context: "SessionContext", layout: PanelLayout) -> None:
        edge_wrapper = context.active_edge
        if edge_wrapper is None:
            return

        state = edge_wrapper._state

        # Error Section (if present, expandable, default open)
        error = state.get_error()
        if error and isinstance(error, HaywireException):
            with ui.card().classes("w-full p-3").style(
                "background: var(--hw-bg-surface);"
                " border: 1px solid var(--hw-danger);"
            ):
                ui.label(f"Category: {error.category}").classes(
                    "text-xs hw-text-muted ml-2"
                )
                error_render_detail(error)

        # Warning Section (if present, expandable, default open)
        if state.has_warning():
            with (
                ui.expansion("Warnings", value=True)
                .classes("w-full")
                .props(
                    "dense dense-toggle"
                    ' header-class="text-xs font-bold uppercase tracking-wide'
                    ' px-2 py-0 min-h-[24px]"'
                )
                .style("color: var(--hw-warning);")
            ):
                with ui.card().classes("w-full p-3").style(
                    "background: var(--hw-bg-surface);"
                    " border: 1px solid var(--hw-warning);"
                ):
                    with ui.column():
                        for warning in state.warnings:
                            ui.label(f"⚠ {warning}").classes("text-xs hw-text-muted ml-2")

        # Adapter Chain Section (if available, expandable, default closed)
        if edge_wrapper.edge.chain_adapter_keys:
            with (
                ui.expansion("Adapter Chain", value=False)
                .classes("w-full")
                .props(
                    "dense dense-toggle"
                    ' header-class="text-xs font-bold hw-text-muted uppercase tracking-wide'
                    ' px-2 py-0 min-h-[24px]"'
                )
            ):
                with ui.card().classes("w-full").style(
                    "background: var(--hw-bg-surface); border: 1px solid var(--hw-border);"
                ):
                    for i, adapter_key in enumerate(edge_wrapper.edge.chain_adapter_keys, 1):
                        ui.label(f"{i}. {adapter_key}").classes("text-xs hw-text-body")

        # Execution Statistics Section (expandable, default closed)
        if state.execution_count > 0:
            with (
                ui.expansion("Execution Statistics", value=False)
                .classes("w-full")
                .props(
                    "dense dense-toggle"
                    ' header-class="text-xs font-bold hw-text-muted uppercase tracking-wide'
                    ' px-2 py-0 min-h-[24px]"'
                )
            ):
                with ui.card().classes("w-full").style(
                    "background: var(--hw-bg-surface); border: 1px solid var(--hw-border);"
                ):
                    ui.label(f"Execution Count: {state.execution_count}").classes(
                        "text-xs hw-text-body"
                    )
                    avg_time = state.average_execution_time_us
                    if avg_time > 0:
                        ui.label(f"Average Time: {avg_time:.1f} μs").classes(
                            "text-xs hw-text-body"
                        )
                    else:
                        ui.label("Average Time: Not measured").classes("text-xs hw-text-dim")
                    ui.label(f"Tested value: {state.example_test_value}").classes(
                        "text-xs hw-text-muted ml-2"
                    )
                    ui.label(f"Tested result: {state.example_test_result}").classes(
                        "text-xs hw-text-muted ml-2"
                    )

        # Connection Path Section (expandable, default open)
        with (
            ui.expansion("Connection Path", value=False)
            .classes("w-full")
            .props(
                "dense dense-toggle"
                ' header-class="text-xs font-bold hw-text-muted uppercase tracking-wide'
                ' px-2 py-0 min-h-[24px]"'
            )
        ):
            with ui.card().classes("w-full p-3").style(
                "background: var(--hw-bg-surface); border: 1px solid var(--hw-border);"
            ):
                ui.label(f"From: {edge_wrapper.source_node_id}").classes(
                    "text-xs hw-text-body ml-2"
                )
                ui.label(f"Port: {edge_wrapper.outlet_port_id}").classes(
                    "text-xs hw-text-dim ml-4"
                )
                ui.label(f"To: {edge_wrapper.sink_node_id}").classes(
                    "text-xs hw-text-body ml-2 mt-1"
                )
                ui.label(f"Port: {edge_wrapper.inlet_port_id}").classes(
                    "text-xs hw-text-dim ml-4"
                )

