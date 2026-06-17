# barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py
"""
NodePortsPanel — lists inlet, outlet, and config ports on the selected node.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.core.session.signals import (
    ActiveGraphMoved,
    GraphDataMutated,
    SelectionMoved,
)
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.utils import anchor_cleanup_to_element

from ....focuses import PortFocus
from ....state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def _type_name(port: object) -> str:
    """Human-readable data-type name for a port's read-only metadata row."""
    port_type = getattr(port, "data_type", None)
    return port_type.__class__.__name__ if port_type else "—"


@panel(
    focus=PortFocus,
    label="Ports",
    icon=hui.icon.node_ports,
    default_open=False,
    order=20,
    redraw_on=(SelectionMoved, GraphDataMutated, ActiveGraphMoved),
)
class NodePortsPanel(BasePanel):
    """Displays the inlet, outlet, and config ports of the selected node.

    Widget lifecycle note: PropertiesEditor builds a fresh panel instance on
    every redraw (``panel_cls().draw(...)`` after ``content.clear()``), so the
    panel cannot own widget cleanup via instance state. Instead each rendered
    widget's container element carries its own teardown (see
    ``_anchor_cleanup_to_element``), which NiceGUI fires on both redraw
    (``content.clear()``) and page close (``client.remove_all_elements``).
    """

    def _render_port(self, port, node_id: str, widget_factory) -> None:
        """Render one port: its live widget (label above) when one applies,
        otherwise a read-only id/type metadata row.

        Honours should_show_widget() — the same predicate the Skin uses — so the
        two surfaces stay semantically identical (a linked inlet / an outlet
        shows no widget here either). A narrow try/except keeps one failing port
        from blanking the whole panel; widget-render failures are already
        isolated by WidgetFactory.render_widget (it returns an inline error
        element rather than raising). The namespaced 'panel:<node_id>' key keeps
        this panel's hot-reload tracking separate from the Skin's, so the Skin
        tearing down the node card (unregister_widget_for_node(node_id)) can't
        clobber it.

        Widget cleanup is anchored to the per-widget container element (see
        ``_anchor_cleanup_to_element``), not to this panel instance, because the
        panel is rebuilt fresh on every redraw.
        """
        try:
            shows_widget = (
                widget_factory is not None and port.widget_key is not None and port.should_show_widget()
            )
            if shows_widget:
                container = ui.column().classes("w-full gap-0 compact-fields")
                with container:
                    ui.label(port.label).classes("text-xs hw-text-dim px-2 pt-1")
                    instance, _element = widget_factory.render_widget(
                        registry_key=port.widget_key,
                        port=port,
                        node_id=f"panel:{node_id}",
                    )
                if instance is not None:
                    # BaseWidget.cleanup() is idempotent, so this composes safely
                    # with the page-disconnect cleanup the widget registers itself.
                    anchor_cleanup_to_element(container, instance.cleanup)
            else:
                hui.info_row(str(port.id), _type_name(port))
        except Exception:
            hui.error_label(f"Error rendering port '{getattr(port, 'id', '?')}'")

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return

        widget_factory = getattr(ctx.app, "widget_factory", None)

        with layout:
            try:
                hw_node = node.node if hasattr(node, "node") else None
                if hw_node is None:
                    hui.empty_state("No port data available", icon=hui.icon.node_ports)
                    return

                # BaseNode stores every port in a single `ports` dict and exposes
                # direction via is_inlet()/is_outlet()/is_config() — there is no
                # `.inlets`/`.outlets` attribute. Mirror the node card by reading
                # the same visible-port set the skins render (get_visible_ports),
                # then classify each port the way render_port() does.
                if hasattr(hw_node, "get_visible_ports"):
                    visible_ports = hw_node.get_visible_ports()
                else:
                    visible_ports = list(getattr(hw_node, "ports", {}).values())
                inlets = [p for p in visible_ports if p.is_inlet()]
                outlets = [p for p in visible_ports if p.is_outlet()]
                configs = [p for p in visible_ports if p.is_config()]

                node_id = getattr(node, "node_id", "")

                # Persist each section's open/closed state via the editor-owned
                # bag threaded through PanelLayout. The panel_key omits the node
                # id on purpose: section expansion is a per-section-type
                # preference that stays stable as you select different nodes
                # (see UI state scope decision), not a per-node setting.
                state_bag = layout.state_bag

                if configs:
                    with hui.expansion_section(
                        label=f"Config ({len(configs)})",
                        default_open=True,
                        state=state_bag,
                        panel_key="node:ports:config",
                    ):
                        for port in configs:
                            self._render_port(port, node_id, widget_factory)

                if inlets:
                    with hui.expansion_section(
                        label=f"Inlets ({len(inlets)})",
                        default_open=True,
                        state=state_bag,
                        panel_key="node:ports:inlets",
                    ):
                        for port in inlets:
                            self._render_port(port, node_id, widget_factory)

                if outlets:
                    with hui.expansion_section(
                        label=f"Outlets ({len(outlets)})",
                        default_open=True,
                        state=state_bag,
                        panel_key="node:ports:outlets",
                    ):
                        for port in outlets:
                            self._render_port(port, node_id, widget_factory)

            except Exception:
                # Structural backstop (Q11): a malformed node / port collection
                # must not throw through the panel host. Per-port failures are
                # handled inside _render_port; this catches everything above the
                # port loops.
                hui.error_label("Error reading ports")
