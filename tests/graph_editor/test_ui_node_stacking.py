"""A card's container carries its node's stacking order as its z-index, restyled with no redraw."""

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
from haywire.core.node.layout import PATCH, STAGE, LayoutChannel
from haywire.ui.components.graph.canvas import GraphCanvasVue
from haywire.ui.skin.factory import SkinFactory

from tests.conftest import edit_route, make_node

pytestmark = pytest.mark.integration


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


def _card(library_system, graph: BaseGraph, channel: LayoutChannel) -> tuple[UINode, Any]:
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    wrapper = make_node(graph, TestAddFloatNode.class_identity.registry_key)
    wrapper.node.props.on_stage = True
    graph._validation.force_immediate_validation()
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        container = ui.element("div")
        ui_node = UINode(
            container,
            wrapper,
            library_system.injector.get(SkinFactory),
            edit_route(Editor(graph, library_system.get_node_factory())),
            channel=channel,
        )
        ui_node.refresh(ChangeReason.NODE_ADDED)
    return ui_node, wrapper


@pytest.fixture
def card(library_system, held_graph: BaseGraph) -> Iterator[tuple[UINode, Any, BaseGraph]]:
    ui_node, wrapper = _card(library_system, held_graph, PATCH)
    yield ui_node, wrapper, held_graph
    ui_node.teardown_subscriptions()


def test_the_container_carries_the_nodes_z(card):
    ui_node, wrapper, _ = card
    assert ui_node.container._style.get("z-index") == "0"

    drawn = ui_node.current_ui_card
    wrapper.node.props.z = 7
    assert ui_node.container._style.get("z-index") == "7"
    assert ui_node.current_ui_card is drawn


def test_a_stage_card_reads_stage_z(library_system, held_graph: BaseGraph):
    ui_node, wrapper = _card(library_system, held_graph, STAGE)
    try:
        wrapper.node.props.z = 9
        wrapper.node.props.stage_z = 3
        assert ui_node.container._style.get("z-index") == "3"
    finally:
        ui_node.teardown_subscriptions()


@pytest.mark.parametrize("how", ["reset", "hot_reload"])
def test_stacking_follows_the_node_across_a_rebuild(card, how: str):
    ui_node, wrapper, graph = card
    old = wrapper.node
    if how == "reset":
        graph.request_node_reset(wrapper.node_id)
    else:
        graph._validation.mark_node_dirty(wrapper.node_id, ChangeReason.NODE_HOT_RELOADED)
    graph._validation.force_immediate_validation()
    assert wrapper.node is not old
    ui_node.refresh(ChangeReason.NODE_HOT_RELOADED)

    wrapper.node.props.z = 4
    assert ui_node.container._style.get("z-index") == "4"


def test_a_stage_canvas_is_marked():
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        assert GraphCanvasVue(stage=True)._props.get("data-hw-stage")
        assert "data-hw-stage" not in GraphCanvasVue()._props


def test_a_stage_canvas_never_magnifies_on_hover():
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        stage, patch_ = GraphCanvasVue(stage=True), GraphCanvasVue()
        assert stage._props["hover-scale-enabled"] is False
        for canvas in (stage, patch_):
            canvas._on_setting_changed("hover_scale_enabled", True, False)
        assert stage._props["hover-scale-enabled"] is False
        assert patch_._props["hover-scale-enabled"] is True
