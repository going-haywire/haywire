"""The edge Style panels' shared subject: which edges one edit reaches, and how it reaches them."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from nicegui import ui

from haywire.ui.panel.render_utils import render_settings
from haywire.ui.utils import anchor_cleanup_to_element

from ..state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.edge.edge_wrapper import EdgeWrapper
    from haywire.core.session.context import SessionContext
    from haywire.core.settings import EdgeSettings


def style_group(ctx: "SessionContext") -> "list[EdgeWrapper]":
    """Return the edges a style edit reaches, the active edge first; empty when it has no style.

    The group is the whole selection when the active edge is selected, only edges
    are selected and every one has a style bag of the active edge's class.
    Otherwise it is the active edge alone.
    """
    edit = ctx.data[EditState]
    active = edit.active_edge
    if active is None or active.style is None:
        return []
    selected = getattr(edit, "selected_edges", None) or set()
    graph = getattr(edit, "active_graph", None)
    if graph is None or active.edge_id not in selected or getattr(edit, "selected_nodes", None):
        return [active]
    group = [active]
    for edge_id in selected:
        if edge_id == active.edge_id:
            continue
        wrapper = graph.get_edge_wrapper(edge_id)
        if wrapper is None or type(wrapper.style) is not type(active.style):
            return [active]
        group.append(wrapper)
    return group


def selection_shares_style(ctx: "SessionContext") -> bool:
    """True when edges alone are selected and one style edit reaches all of them."""
    edit = ctx.data[EditState]
    selected = getattr(edit, "selected_edges", None) or set()
    return bool(selected) and len(style_group(ctx)) == len(selected)


def render_edge_style(ctx: "SessionContext", group: "list[EdgeWrapper]") -> None:
    """Render the style fields of ``group[0]``; a change to a field is written to the rest of the group.

    A field the first edge resets is reset on the others.
    """
    lead = group[0].style
    if lead is None:
        return
    with ui.column().classes("w-full gap-0") as column:
        render_settings(ctx, lead)
    peers = [w.style for w in group[1:] if w.style is not None]
    if not peers:
        return
    fan_out = _fan_out_to(lead, peers)
    lead._subscribe(fan_out)
    anchor_cleanup_to_element(column, lambda: lead._unsubscribe(fan_out))


def _fan_out_to(lead: "EdgeSettings", peers: "list[EdgeSettings]") -> "Callable[[str, Any, Any], None]":
    """Return a change callback for *lead* that copies each field it changes onto *peers*."""

    def _fan_out(name: str, value: Any, _old: Any) -> None:
        for bag in peers:
            if lead._is_locally_set(name):
                setattr(bag, name, value)
            else:
                bag._reset(name)

    return _fan_out
