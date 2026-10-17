"""What a selection-wide settings form edits: one element's own bag, or a neutral form for several.

The rule shared by node Appearance and edge Style on the selection surfaces:

- **Cross-kind** selection (nodes and edges): the form does not apply and is hidden.
- **Non-uniform** selection (edges of different style classes or without a style,
  reroute nodes among the nodes): the form is greyed, with the reason.
- **One element**: the form edits that element's own bag.
- **Several**: the form edits a **neutral form** — a standalone bag of the shared
  class, opened with defaults, whose every change is written to each selected
  element and whose resets reset each one. A header says so.

The properties inspector does not use this: it edits the active element only.

Either form writes through the edit route of the level on screen, so it writes
only in level mode edit; each write to a real bag marks the graph unsaved as a
Properties form's does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Literal

from nicegui import ui

from haywire.core.access import LevelMode
from haywire.core.di.context import get_settings_registry
from haywire.core.node.properties import NodeProperties
from haywire.ui import elements as hui
from haywire.ui.panel.render_utils import render_settings
from haywire.ui.utils import anchor_cleanup_to_element

from ..state.edit_state import EditState
from ..state.graph_app_state import route_for

if TYPE_CHECKING:
    from haywire.core.graph.edit_route import EditRoute
    from haywire.core.session.context import SessionContext
    from haywire.core.settings.settings import Settings

Status = Literal["hidden", "greyed", "own", "neutral"]


@dataclass
class FormSubject:
    """What a selection-wide form edits, and whether it is drawn at all.

    ``status`` is ``hidden`` (not drawn), ``greyed`` (drawn disabled, ``reason`` says
    why), ``own`` (``bags`` holds the one element's bag) or ``neutral`` (``bags``
    holds every selected element's bag, all of class ``bag_class``).
    """

    status: Status
    reason: str = ""
    bags: "list[Settings]" = field(default_factory=list)
    bag_class: "type[Settings] | None" = None
    noun: str = ""

    @property
    def editable(self) -> bool:
        return self.status in ("own", "neutral")


def edge_style_subject(ctx: "SessionContext") -> FormSubject:
    """Return what the edge Style form edits for the current selection."""
    edit = ctx.data[EditState]
    graph = edit.active_graph
    if graph is None or not edit.selected_edges or edit.selected_nodes:
        return FormSubject("hidden")
    wrappers = [graph.get_edge_wrapper(edge_id) for edge_id in sorted(edit.selected_edges)]
    styles = [w.style if w is not None else None for w in wrappers]
    present: "list[Settings]" = [s for s in styles if s is not None]
    if not present:
        return FormSubject("hidden")
    if len(present) < len(styles):
        return FormSubject("greyed", reason="Some selected edges have no style")
    if len({type(s) for s in present}) > 1:
        return FormSubject("greyed", reason="Selected edges have different style types")
    if len(present) == 1:
        return FormSubject("own", bags=present, noun="edge")
    return FormSubject("neutral", bags=present, bag_class=type(present[0]), noun="edges")


def node_appearance_subject(ctx: "SessionContext") -> FormSubject:
    """Return what the node Appearance form edits for the current selection."""
    edit = ctx.data[EditState]
    graph = edit.active_graph
    if graph is None or not edit.selected_nodes or edit.selected_edges:
        return FormSubject("hidden")
    nodes = []
    for node_id in sorted(edit.selected_nodes):
        wrapper = graph.get_node_wrapper(node_id)
        node = getattr(wrapper, "node", None) if wrapper is not None else None
        if wrapper is None or node is None:
            return FormSubject("hidden")
        nodes.append(node)
    reroutes = [n for n in nodes if n.behavior.is_reroute_node]
    if len(nodes) == 1:
        # A lone reroute or locked node has no appearance to edit here.
        if reroutes or nodes[0].props.locked is True:
            return FormSubject("hidden")
        return FormSubject("own", bags=[nodes[0].props], noun="node")
    if reroutes:
        return FormSubject("greyed", reason="Selection contains reroute nodes")
    bags = [n.props for n in nodes]
    # Each node class has its own props subclass; the shared base holds every appearance field.
    classes = {type(b) for b in bags}
    bag_class = classes.pop() if len(classes) == 1 else NodeProperties
    return FormSubject("neutral", bags=bags, bag_class=bag_class, noun="nodes")


def render_form(
    ctx: "SessionContext",
    subject: FormSubject,
    *,
    categories: "tuple[str, ...] | None" = None,
    graph: Any = None,
) -> None:
    """Render *subject*'s form: its own bag, or a neutral form fanning out to every bag.

    *graph* attaches the neutral bag to that graph, so its graph-mirror fields show
    the graph's values — what a reset returns each element to.
    """
    route = route_for(ctx)
    if route is None:
        return  # no level open: a graph-document bag is never drawn writable
    if subject.status == "own":
        render_settings(ctx, subject.bags[0], categories=categories, route=route)
        return
    if subject.status != "neutral" or subject.bag_class is None:
        return
    neutral = subject.bag_class(registry=get_settings_registry())
    if graph is not None:
        # _owning_graph() reads _graph first, so the mirrors track this graph.
        neutral._graph = graph  # type: ignore[attr-defined]
    neutral._subscribe_settings()
    default_word = "the graph's defaults" if graph is not None else "defaults"
    with ui.column().classes("w-full gap-0") as column:
        header = f"Editing {len(subject.bags)} {subject.noun} — fields show {default_word}"
        ui.label(f"{header}; a change applies to all.").classes("text-xs hw-text-muted px-2 py-1")
        render_settings(ctx, neutral, categories=categories, route=route)
    fan_out = fan_out_to(neutral, subject.bags, route)
    neutral._subscribe(fan_out)
    anchor_cleanup_to_element(column, neutral._cleanup)


def fan_out_to(
    neutral: "Settings", bags: "list[Settings]", route: "EditRoute"
) -> "Callable[[str, Any, Any], None]":
    """Return a change callback for *neutral* that applies each user edit to every bag in *bags*.

    A value the user sets is set on every bag; a field the user resets is reset on
    every bag, as one undo step per edit. Each write goes through *route* and needs level mode ``EDIT``; a
    refused one leaves that bag as it was. A mirror field following its source
    changes nothing.
    """
    was_set: dict[str, bool] = {}

    def _fan_out(name: str, value: Any, _old: Any) -> None:
        now_set = neutral._is_locally_set(name)
        before = was_set.get(name, False)
        was_set[name] = now_set
        if now_set:
            route.set_settings(bags, name, value, minimum=LevelMode.EDIT)
        elif before:
            route.reset_settings(bags, name, minimum=LevelMode.EDIT)

    return _fan_out


def disabled_icon(icon: str, tooltip: str) -> None:
    """Draw a toolbar icon greyed out, its tooltip giving the reason."""
    # The tooltip sits on a wrapper: the dimmed button takes no pointer events,
    # so a tooltip on the button itself would never show.
    with ui.element("span").classes("hw-disabled inline-flex") as wrapper:
        hui.icon_action(icon).style("opacity: 0.4; pointer-events: none")
    wrapper.tooltip(tooltip)
