"""A card draws with the skin of its view: ``props.skin`` in the patch, ``props.stage_skin`` on a stage."""

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


def _card(library_system, graph: BaseGraph, wrapper, channel: LayoutChannel) -> UINode:
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
    return ui_node


@pytest.fixture
def views(library_system, held_graph: BaseGraph) -> Iterator[tuple[UINode, UINode, Any]]:
    """The same on-stage node drawn by a patch card and a stage card."""
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    wrapper = make_node(held_graph, TestAddFloatNode.class_identity.registry_key)
    wrapper.node.props.on_stage = True
    held_graph._validation.force_immediate_validation()
    patch_card = _card(library_system, held_graph, wrapper, PATCH)
    stage_card = _card(library_system, held_graph, wrapper, STAGE)
    yield patch_card, stage_card, wrapper
    patch_card.teardown_subscriptions()
    stage_card.teardown_subscriptions()


def _pin_ids(ui_node: UINode) -> set[str]:
    return {e._props["data-pin-id"] for e in ui_node.container.descendants() if "data-pin-id" in e._props}


def _key(name: str) -> str:
    import haybale_graph_editor.skins.split_skin as split
    import haybale_graph_editor.skins.stacked_skin as stacked

    cls = {"stacked": stacked.StackedNodeSkin, "split": split.SplitNodeSkin}[name]
    return cls.class_identity.registry_key


def _data_pins(wrapper) -> set[str]:
    return {p.id for p in wrapper.node.ports.values() if p.has_pin()}


def test_both_cards_default_to_the_default_skin_and_the_stage_card_is_drawn_for_a_stage(views) -> None:
    patch_card, stage_card, wrapper = views

    assert patch_card._skin_key() == _key("stacked")
    assert stage_card._skin_key() == _key("stacked")
    assert _data_pins(wrapper) <= _pin_ids(patch_card)
    assert not _data_pins(wrapper) & _pin_ids(stage_card)


def test_a_stage_skin_change_redraws_with_the_new_skin_in_the_stage_view_only(views) -> None:
    patch_card, stage_card, wrapper = views
    patch_pins = _pin_ids(patch_card)

    wrapper.node.props.stage_skin = _key("split")
    for card in (patch_card, stage_card):
        with card.container.client:
            card.refresh(ChangeReason.NODE_REDRAW_REQUESTED)

    assert stage_card._skin_key() == _key("split")
    assert patch_card._skin_key() == _key("stacked")
    assert _pin_ids(patch_card) == patch_pins
    assert not _data_pins(wrapper) & _pin_ids(stage_card)


def test_a_default_skin_ignores_detail_on_stage_only(views) -> None:
    patch_card, stage_card, wrapper = views

    wrapper.node.props.detail = "pins"

    assert patch_card.container._props["data-node-props-detail"] == "pins"
    assert stage_card.container._props["data-node-props-detail"] == "full"


def test_an_untouched_graph_saves_no_stage_skin_keys(views, held_graph: BaseGraph) -> None:
    _patch_card, _stage_card, wrapper = views

    node_values = wrapper.serialize()["node_data"]["props"]["values"]
    assert "stage_skin" not in node_values
    assert "default_stage_skin" not in held_graph.to_dict()["props"]["values"]
