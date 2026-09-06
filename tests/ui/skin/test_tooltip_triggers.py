"""Tooltip triggers on a card must be small, and must never nest.

Each ``add_pin_tooltip`` trigger costs a websocket round trip on EVERY hover
crossing — ``mouseenter`` shows, ``mouseleave`` hides, both server-side. That is
survivable for a pin-sized target the user aims at deliberately. It is not
survivable when the trigger is a container: a port's content column spans its
label and widget, a config row spans the full card width, and both CONTAIN the
widget, so one pointer movement fires enters and leaves on several of them at
once — several round trips, several Quasar tooltips shown and torn down, for a
single crossing.

Panning is what makes that bite. The content moves under a stationary cursor,
so a gesture generates crossings by itself, and each one lands in the middle of
the frames the gesture needs. Measured by hand in Firefox on a 300-node graph:
~0.5s of freeze at the start of a pan begun with the cursor over a card BODY,
and never over the title strip — the one part of a card that carried no
tooltip. Chrome did not show it. Removing the nested triggers removed the
freeze entirely.

These tests pin the SHAPE, not the timing — a timing assertion on a canvas this
size is a flake, and the shape is what actually went wrong:

  * no trigger contains another trigger
  * no trigger is a layout container
  * triggers still exist (a card that lost its tooltips passes every
    "is it fast" check ever written)
  * a built tooltip animates instantly
"""

from __future__ import annotations

import pytest
from nicegui import ui

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.ui.skin.factory import SkinFactory

pytestmark = [pytest.mark.integration]

#: Classes that mark a LAYOUT container — something that wraps a label and a
#: widget. A tooltip trigger must never be one of these.
_CONTAINER_CLASSES = ("compact-fields", "node-card", "nicegui-row", "nicegui-column")


def _graph():
    return BaseGraph(filestem="tooltip triggers", validation_scheduler=SyncScheduler())


def _node(graph):
    """A node with widget-bearing inlets AND a config port, so both tooltip
    call sites in the studio skin are exercised by one render."""
    from haybale_testing.nodes.testbed.test_performance import PerformanceTester

    wrapper = graph.create_node_wrapper(PerformanceTester.class_identity.registry_key, position=(0, 0))
    assert wrapper is not None
    wrapper.node.ports["port_count"].set_value(3)
    graph.force_validation()
    return wrapper


@pytest.fixture
def rendered(library_system, nicegui_slot_context):
    skin_factory = library_system.injector.get(SkinFactory)
    graph = _graph()
    wrapper = _node(graph)
    skin_key = skin_factory._skin_registry.get_default_skin_registry_key()
    assert skin_key, "no default skin registered"
    container = ui.element("div")
    with container:
        skin_factory.render(skin_registry_key=skin_key, wrapper=wrapper)
    return container


def _triggers(container: ui.element) -> list[ui.element]:
    """Every element carrying a hover listener — i.e. every tooltip trigger."""
    return [
        el
        for el in container.descendants()
        if any(listener.type == "mouseenter" for listener in el._event_listeners.values())
    ]


def _is_ancestor(candidate: ui.element, element: ui.element) -> bool:
    parent = element.parent_slot.parent if element.parent_slot else None
    while parent is not None:
        if parent is candidate:
            return True
        parent = parent.parent_slot.parent if parent.parent_slot else None
    return False


def test_a_card_still_has_tooltip_triggers(rendered) -> None:
    """Guard the guards: deleting every tooltip would satisfy the two tests
    below trivially, and would look like a performance win."""
    assert _triggers(rendered), "the card carries no tooltip triggers at all"


def test_no_tooltip_trigger_contains_another(rendered) -> None:
    triggers = _triggers(rendered)
    nested = [
        (outer, inner)
        for outer in triggers
        for inner in triggers
        if outer is not inner and _is_ancestor(outer, inner)
    ]
    assert not nested, (
        "a tooltip trigger contains another, so one pointer movement fires "
        "several hover round trips: "
        + ", ".join(f"{sorted(outer._classes)} contains {sorted(inner._classes)}" for outer, inner in nested)
    )


def test_no_tooltip_trigger_is_a_layout_container(rendered) -> None:
    offenders = [el for el in _triggers(rendered) if any(cls in el._classes for cls in _CONTAINER_CLASSES)]
    assert not offenders, (
        "a tooltip trigger is a layout container spanning a label and a widget, "
        "so it fires wherever the pointer crosses the card body: "
        + ", ".join(sorted(str(sorted(el._classes)) for el in offenders))
    )


def test_a_built_tooltip_animates_instantly(rendered) -> None:
    """Hiding a VISIBLE tooltip is the one tooltip operation that can land in
    the middle of a pan, and Quasar's default 300ms show/hide animation makes
    it an animation the browser runs while the canvas transforms underneath.
    Firefox froze on exactly that; Chrome did not. Instant transitions fixed it.
    """
    triggers = _triggers(rendered)
    assert triggers, "no trigger to build a tooltip from"

    # The tooltip is built lazily on first hover, so fire the handler the way a
    # hover would rather than reaching past it.
    trigger = triggers[0]
    listener = next(
        listener for listener in trigger._event_listeners.values() if listener.type == "mouseenter"
    )
    assert listener.handler is not None
    listener.handler(None)

    tooltips = [el for el in trigger.descendants() if el.tag == "q-tooltip"]
    assert tooltips, "hovering a trigger built no tooltip"
    props = tooltips[0]._props
    assert str(props.get("transition-duration")) == "0", (
        "the tooltip animates its show/hide; a hide landing mid-gesture then "
        f"runs an animation over the moving canvas (props={props})"
    )
