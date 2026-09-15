# barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node_ports.py
"""
NodePortsPanel — lists inlet, outlet, and config ports on the selected node.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

# Importing the class registers "nicegui-sortable" as an ESM module. A page's
# importmap is written when the page is served, and `make_sortable` imports the
# class only at render time — too late for a page already in the browser, whose
# bare specifier then fails to resolve.
from nicegui.elements.sortable.sortable import Sortable as _Sortable  # noqa: F401

from haywire.core.signals import (
    ActiveGraphMoved,
    GraphDataMutated,
    SelectionMoved,
)
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.utils import anchor_cleanup_to_element

from ....surfaces import PortInspector
from ....state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


_DRAG_HANDLE_CLASS = "hw-port-drag-handle"
"""Marks the grip element SortableJS accepts a drag from (its ``handle`` selector)."""


def _type_name(port: object) -> str:
    """Human-readable data-type name for a port's read-only metadata row."""
    port_type = getattr(port, "data_type", None)
    return port_type.__class__.__name__ if port_type else "—"


@panel(
    surface=PortInspector,
    label="Ports",
    icon=hui.icon.node_ports,
    default_open=True,
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

    def _render_lane(
        self,
        node,
        ports: list,
        lane: str,
        node_id: str,
        widget_factory,
        parent_fold: str | None = None,
        depth: int = 0,
    ) -> None:
        """Render the ports whose fold is ``parent_fold``, recursing into folds.

        One sibling group per call — the ports a user may rearrange among
        themselves. A fold's children follow its own row, indented one level
        and in a sortable of their own.

        Each row is dragged by its grip alone, so a row whose body is a widget
        stays editable: a whole-row drag would swallow every click into the
        field.

        Args:
            node: The ``BaseNode``, threaded rather than held on ``self``: the
                panel is rebuilt on every redraw and owns no instance state.
            ports: Every port of the lane, folded children included.
            lane: ``"config"``, ``"inlet"`` or ``"outlet"``, supplied by the
                section that owns this list. Never read off a port — a fold is
                itself a CONFIG port and would misreport its lane.
            depth: Fold nesting level, which sets this group's indentation.
        """
        siblings = [p for p in ports if p.parent_fold == parent_fold]
        if not siblings:
            return

        sibling_ids = [p.id for p in siblings]

        # One row per sibling, each paired with the block its children go in, so
        # a fold's children sit directly under it. The rows all belong to this
        # group's sortable; the child blocks sit outside it, which is what keeps
        # a child from being dropped among its parent's siblings.
        container = ui.column().classes("w-full gap-0").style(f"padding-left: {depth * 12}px;")
        child_slots: list[tuple[Any, ui.column]] = []
        with container:
            for port in siblings:
                with ui.column().classes("w-full gap-0"):
                    with ui.row().classes("w-full items-start gap-0 flex-nowrap min-w-0"):
                        ui.icon(hui.icon.drag_handle).classes(
                            f"{_DRAG_HANDLE_CLASS} text-sm hw-text-dim shrink-0 mt-1 cursor-grab"
                        )
                        with ui.column().classes("flex-1 min-w-0 gap-0"):
                            if port.is_fold:
                                ui.label(port.label).classes("text-xs hw-text-dim px-2 pt-1")
                            else:
                                self._render_port(port, node_id, widget_factory)
                    if port.is_fold:
                        child_slots.append((port, ui.column().classes("w-full gap-0")))

        container.make_sortable(
            group=self._sortable_group(node_id, lane, parent_fold),
            handle=f".{_DRAG_HANDLE_CLASS}",
            on_end=lambda e, n=node, ids=sibling_ids: self._on_reorder(n, ids, e),
        )

        for port, slot in child_slots:
            with slot:
                self._render_lane(node, ports, lane, node_id, widget_factory, port.id, depth + 1)

    @staticmethod
    def _sortable_group(node_id: str, lane: str, parent_fold: str | None) -> str:
        """Return the SortableJS group name for one sibling group.

        Unique per (node, lane, fold), which is what makes a cross-lane or
        cross-fold drop inexpressible rather than something to validate.
        """
        return f"hw-ports:{node_id}:{lane}:{parent_fold or 'root'}"

    def _on_reorder(self, node, sibling_ids: list[str], event) -> None:
        """Apply a completed drop: move one id and hand the new order to the node.

        NiceGUI's own ``on_end`` has already re-parented the element before this
        runs, so the DOM is correct and this only writes the model to match. No
        signal is published — this panel redraws on a data mutation and would
        rebuild its own list mid-gesture. The node marks itself dirty as
        ``NODE_LAYOUT_CHANGED``, which repaints the card and records the change
        for the save.

        Args:
            sibling_ids: The group's ids in the order they were rendered.
            event: A ``SortableEventArguments``, whose indices address
                ``sibling_ids``.
        """
        old_index = event.old_index
        new_index = event.new_index
        if old_index == new_index:
            return
        if not (0 <= old_index < len(sibling_ids)) or not (0 <= new_index < len(sibling_ids)):
            return
        reordered = list(sibling_ids)
        reordered.insert(new_index, reordered.pop(old_index))
        node.reorder_ports(reordered)

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
                # `.inlets`/`.outlets` attribute.
                #
                # get_all_ports, not get_visible_ports: the latter drops every
                # port under a collapsed fold, which would make a closed fold's
                # children unreorderable. The card and the panel legitimately
                # show different sets.
                if hasattr(hw_node, "get_all_ports"):
                    visible_ports = hw_node.get_all_ports()
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
                        self._render_lane(hw_node, configs, "config", node_id, widget_factory)

                if inlets:
                    with hui.expansion_section(
                        label=f"Inlets ({len(inlets)})",
                        default_open=True,
                        state=state_bag,
                        panel_key="node:ports:inlets",
                    ):
                        self._render_lane(hw_node, inlets, "inlet", node_id, widget_factory)

                if outlets:
                    with hui.expansion_section(
                        label=f"Outlets ({len(outlets)})",
                        default_open=True,
                        state=state_bag,
                        panel_key="node:ports:outlets",
                    ):
                        self._render_lane(hw_node, outlets, "outlet", node_id, widget_factory)

            except Exception:
                # Structural backstop (Q11): a malformed node / port collection
                # must not throw through the panel host. Per-port failures are
                # handled inside _render_port; this catches everything above the
                # port loops.
                hui.error_label("Error reading ports")
