"""A card's prop subscriptions follow its node across a rebuild (Reset, hot reload)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest
from nicegui import Client, ui

from haybale_graph_editor.editors.graph_canvas.ui_node import UINode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.types import ChangeReason
from haywire.ui.skin.factory import SkinFactory

from tests.conftest import edit_route, make_node


def _noop_page() -> None:
    pass


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


@pytest.fixture
def card(library_system, held_graph: BaseGraph) -> Iterator[tuple[UINode, Any, BaseGraph]]:
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    wrapper = make_node(held_graph, TestAddFloatNode.class_identity.registry_key)
    held_graph._validation.force_immediate_validation()
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        container = ui.element("div")
        ui_node = UINode(
            container,
            wrapper,
            library_system.injector.get(SkinFactory),
            edit_route(Editor(held_graph, library_system.get_node_factory())),
        )
        ui_node.refresh(ChangeReason.NODE_ADDED)
    yield ui_node, wrapper, held_graph
    ui_node.teardown_subscriptions()


def _rebuild(graph: BaseGraph, wrapper: Any, how: str) -> Any:
    old = wrapper.node
    if how == "reset":
        graph.request_node_reset(wrapper.node_id)
    else:
        graph._validation.mark_node_dirty(wrapper.node_id, ChangeReason.NODE_HOT_RELOADED)
    graph._validation.force_immediate_validation()
    assert wrapper.node is not old, "rebuild must produce a new node instance"
    return wrapper.node


def _refresh(ui_node: UINode) -> None:
    # What on_validated does for a redraw reason.
    ui_node.refresh(ChangeReason.NODE_HOT_RELOADED)


@pytest.mark.integration
@pytest.mark.parametrize("how", ["reset", "hot_reload"])
def test_slot_restyle_follows_the_node_across_a_rebuild(card, how: str):
    ui_node, wrapper, graph = card
    node = _rebuild(graph, wrapper, how)
    _refresh(ui_node)

    node.props.width = 333
    node.props.size_adapt = "manual"

    assert ui_node.container_slot is not None
    assert ui_node.container_slot._style.get("min-width") == "333px"


@pytest.mark.integration
@pytest.mark.parametrize("how", ["reset", "hot_reload"])
def test_locked_attr_follows_the_node_across_a_rebuild(card, how: str):
    ui_node, wrapper, graph = card
    node = _rebuild(graph, wrapper, how)
    _refresh(ui_node)

    node.props.locked = True
    assert ui_node.container._props.get("data-node-props-locked") == "true"
    node.props.locked = False
    assert "data-node-props-locked" not in ui_node.container._props


@pytest.mark.integration
def test_detail_attr_follows_the_node_across_a_rebuild(card):
    ui_node, wrapper, graph = card
    node = _rebuild(graph, wrapper, "reset")
    _refresh(ui_node)
    seen: list[str] = []
    orig = ui_node._apply_detail_attr

    def spy() -> None:
        seen.append("x")
        orig()

    ui_node._apply_detail_attr = spy  # type: ignore[method-assign]
    node.props.detail = "minimal" if node.props.detail != "minimal" else "full"
    assert seen


@pytest.mark.integration
def test_reset_reaches_the_card_through_a_redraw_reason(card):
    _, wrapper, graph = card
    graph.request_node_reset(wrapper.node_id)
    result = graph._validation.force_immediate_validation()
    assert result is not None
    assert result.nodes[wrapper.node_id] is ChangeReason.NODE_RESET_REQUESTED
    assert wrapper.node_id in result.get_nodes_requiring_redraw()


@pytest.mark.integration
def test_reset_after_a_manual_resize_clears_the_slot_size(card):
    ui_node, wrapper, graph = card
    node = _rebuild(graph, wrapper, "reset")
    _refresh(ui_node)
    node.props.width = 333
    node.props.size_adapt = "manual"
    assert ui_node.container_slot is not None
    assert ui_node.container_slot._style.get("min-width") == "333px"

    _rebuild(graph, wrapper, "reset")
    _refresh(ui_node)

    assert "min-width" not in ui_node.container_slot._style
