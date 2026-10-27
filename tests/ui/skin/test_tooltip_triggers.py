"""Tooltip triggers on a card must be small, and must never nest.

A tooltip trigger is an element carrying ``data-hw-tip``; the page's hover-tip
script shows the tip while the pointer is over the innermost one. A trigger that
is a container (a port's content column, a config row) shows its tip wherever
the pointer crosses the card body, and nested triggers swap tips on every small
movement, so each trigger is one thing the user points at.

The tips cost the server nothing on hover: a card registers no hover listener.
The old server-side tooltips made a round trip on every crossing and froze the
start of a pan for ~0.5s in Firefox on a 300-node graph.

These tests pin the SHAPE:

  * no trigger contains another trigger
  * no trigger is a layout container
  * triggers still exist (a card that lost its tooltips passes every
    "is it fast" check ever written)
  * a trigger carries its port's text, and no card element listens for hovers
"""

from __future__ import annotations

import pytest
from nicegui import ui

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.ui.hover_tip import TIP_ATTR
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


def _fold_node(graph):
    """A node whose ports sit in folds, so the fold header's tooltip — hosted
    on the header row, triggered by its triangle — is exercised too."""
    from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

    wrapper = graph.create_node_wrapper(FoldProbeNode.class_identity.registry_key, position=(0, 0))
    assert wrapper is not None
    return wrapper


@pytest.fixture(params=[_node, _fold_node], ids=["widgets_and_configs", "folds"])
def rendered(request, library_system, nicegui_slot_context):
    skin_factory = library_system.injector.get(SkinFactory)
    graph = _graph()
    wrapper = request.param(graph)
    skin_key = skin_factory._skin_registry.get_default_skin_registry_key()
    assert skin_key, "no default skin registered"
    container = ui.element("div")
    with container:
        skin_factory.render(skin_registry_key=skin_key, wrapper=wrapper)
    return container


def _triggers(container: ui.element) -> list[ui.element]:
    """Every tooltip trigger: every element carrying the tip's text."""
    return [el for el in container.descendants() if TIP_ATTR in el._props]


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


def test_a_trigger_carries_its_text_and_nothing_listens_for_hovers(rendered) -> None:
    triggers = _triggers(rendered)
    assert all(str(el._props[TIP_ATTR]).strip() for el in triggers), "a trigger carries an empty tip"
    hover_listeners = [
        el
        for el in rendered.descendants()
        if any(listener.type in ("mouseenter", "mouseleave") for listener in el._event_listeners.values())
    ]
    assert not hover_listeners, (
        "a card element listens for hovers on the server, so each crossing costs a round trip: "
        + ", ".join(sorted(str(sorted(el._classes)) for el in hover_listeners))
    )
