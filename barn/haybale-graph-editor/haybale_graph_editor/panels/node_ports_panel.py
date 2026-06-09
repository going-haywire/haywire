# barn/haybale-graph-editor/haybale_graph_editor/panels/node_ports_panel.py
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

from ..focuses import NodeFocus
from ..state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from haywire.ui.widget.interface import IWidget


def _type_name(port: object) -> str:
    """Human-readable data-type name for a port's read-only metadata row."""
    port_type = getattr(port, "data_type", None)
    return port_type.__class__.__name__ if port_type else "—"


@panel(
    focus=NodeFocus,
    label="Ports",
    icon=hui.icon.node_ports,
    default_open=False,
    order=20,
    redraw_on=(SelectionMoved, GraphDataMutated, ActiveGraphMoved),
)
class NodePortsPanel(BasePanel):
    """Displays the inlet, outlet, and config ports of the selected node."""

    def __init__(self) -> None:
        super().__init__()
        # Live widget instances this panel created, keyed by port id. The panel
        # owns their lifecycle: the previous batch is cleaned up at the top of
        # every draw() (redraws + selection changes share this teardown), and a
        # final sweep runs on client disconnect.
        self._widgets: dict[str, "IWidget"] = {}
        self._disconnect_registered: bool = False

    def _dispose_widgets(self) -> None:
        """Clean up every widget instance this panel created, then forget them.

        Called at the top of each draw() before rebuilding, and once on client
        disconnect. BaseWidget.cleanup() is idempotent, so overlapping calls are
        safe. Each cleanup() drops the widget's port.on_changed subscription.
        """
        for widget in self._widgets.values():
            try:
                widget.cleanup()
            except Exception:
                # A widget that fails to clean up must not block the others.
                pass
        self._widgets.clear()

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

        Widget cleanup is anchored to the per-widget container element, NOT to
        this panel instance: PropertiesEditor instantiates a fresh panel object
        on every redraw (``panel_cls().draw(...)`` after ``content.clear()``),
        so an instance-held batch would never get disposed and its
        ``port.on_changed`` subscription would leak on each redraw. Overriding
        the container's ``_handle_delete`` (fired by ``content.clear()`` via the
        client's ``remove_elements``) calls ``widget.cleanup()`` exactly when the
        DOM is torn down, regardless of which panel instance built it.
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
                    self._widgets[port.id] = instance
                    self._anchor_cleanup_to_element(container, instance)
            else:
                hui.info_row(str(port.id), _type_name(port))
        except Exception:
            hui.error_label(f"Error rendering port '{getattr(port, 'id', '?')}'")

    @staticmethod
    def _anchor_cleanup_to_element(element: "ui.element", widget: "IWidget") -> None:
        """Call ``widget.cleanup()`` when ``element`` is deleted from the DOM.

        NiceGUI fires ``Element._handle_delete()`` for every element removed by
        ``content.clear()`` (client.remove_elements). BaseWidget.cleanup() is
        idempotent, so this composes safely with the page-disconnect cleanup the
        widget also registers in render().
        """
        original_handle_delete = element._handle_delete

        def _handle_delete() -> None:
            try:
                widget.cleanup()
            except Exception:
                pass
            original_handle_delete()

        element._handle_delete = _handle_delete  # type: ignore[method-assign]

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        # Dispose the previous batch before building a new one. draw() is the
        # single teardown point: a redraw_on redraw and a selection change both
        # re-enter here, and BaseWidget.cleanup() is idempotent.
        self._dispose_widgets()

        node = ctx.data[EditState].active_node
        if node is None:
            return

        widget_factory = getattr(ctx.app, "widget_factory", None)

        with layout:
            # Register a one-time client-disconnect sweep so the final batch is
            # cleaned up when the page closes (draw() won't run again then).
            if not self._disconnect_registered:
                try:
                    ui.context.client.on_disconnect(self._dispose_widgets)
                    self._disconnect_registered = True
                except Exception:
                    pass

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

                if configs:
                    with hui.expansion_section(label=f"Config ({len(configs)})", default_open=False):
                        for port in configs:
                            self._render_port(port, node_id, widget_factory)

                if inlets:
                    with hui.expansion_section(label=f"Inlets ({len(inlets)})", default_open=False):
                        for port in inlets:
                            self._render_port(port, node_id, widget_factory)

                if outlets:
                    with hui.expansion_section(label=f"Outlets ({len(outlets)})", default_open=False):
                        for port in outlets:
                            self._render_port(port, node_id, widget_factory)

            except Exception:
                # Structural backstop (Q11): a malformed node / port collection
                # must not throw through the panel host. Per-port failures are
                # handled inside _render_port; this catches everything above the
                # port loops.
                hui.error_label("Error reading ports")
