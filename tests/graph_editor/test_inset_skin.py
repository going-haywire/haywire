"""The Inset skin: a Graph-node card whose body shows its interior's stage."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, cast

import pytest
from nicegui import Client, ui

from haybale_graph_editor.editors.graph_canvas.ui_node import UINode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.graph.types import ChangeReason
from haywire.core.node.layout import PATCH, STAGE, LayoutChannel
from haywire.ui.skin.factory import SkinFactory

from tests.conftest import edit_route, make_node

if TYPE_CHECKING:
    from haywire.barn.builtin.nodes.graph_node import GraphNode

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"
_CARD = "haywire-core:node:GraphNode"
_PLACEHOLDER = "Nothing on stage — Enter to arrange"


def _noop_page() -> None:
    pass


def _inset_key() -> str:
    from haybale_graph_editor.skins.inset_skin import InsetSkin

    return InsetSkin.class_identity.registry_key


@pytest.fixture
def group(library_system) -> Iterator[tuple[BaseGraph, Any, SubgraphDefinition, Any]]:
    """A Group card with a one-inlet, one-outlet interface and one staged interior adder."""
    from haybale_testing.types.test_types import TEST_FLOAT

    from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode, SubgraphOutputNode

    graph = BaseGraph(
        filestem="host", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    definition = graph.add_subgraph(SubgraphDefinition(key="sg", label="Group"))
    inlet = make_node(definition, SubgraphInputNode.class_identity.registry_key)
    outlet = make_node(definition, SubgraphOutputNode.class_identity.registry_key)
    with inlet.node.rejig():
        inlet.node.add(TEST_FLOAT.as_outlet("value", label="Value"))
    with outlet.node.rejig():
        outlet.node.add(TEST_FLOAT.as_inlet("result", label="Result"))
    staged = make_node(definition, _ADD)
    staged.node.props.on_stage = True
    card = make_node(graph, _CARD, node_data={"store": {SUBGRAPH_KEY: "sg"}})
    cast("GraphNode", card.node).reconcile_interface()
    card.node.props.skin = _inset_key()
    card.node.props.stage_skin = _inset_key()
    yield graph, card, definition, staged
    graph._validation.clear()
    graph.cleanup()


def _draw(library_system, graph: BaseGraph, wrapper, channel: LayoutChannel) -> UINode:
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        ui_node = UINode(
            ui.element("div"),
            wrapper,
            library_system.injector.get(SkinFactory),
            edit_route(Editor(graph, library_system.get_node_factory())),
            channel=channel,
        )
        ui_node.refresh(ChangeReason.NODE_ADDED)
    return ui_node


def _bodies(ui_node: UINode) -> list[ui.element]:
    return [e for e in ui_node.container.descendants() if "data-hw-inset" in e._props]


def _outside_body(ui_node: UINode) -> list[ui.element]:
    inside = {id(d) for body in _bodies(ui_node) for d in body.descendants()}
    return [e for e in ui_node.container.descendants() if id(e) not in inside]


def _labels(elements: list[ui.element]) -> list[str]:
    return [e.text for e in elements if isinstance(e, ui.label)]


def test_the_inset_is_offered_for_graph_nodes_only(library_system) -> None:
    from haywire.core.skin.settings import (
        _graph_node_patch_skin_choices,
        _graph_node_stage_skin_choices,
        _patch_skin_choices,
        _stage_skin_choices,
    )

    key = _inset_key()
    assert key in _graph_node_patch_skin_choices()
    assert key in _graph_node_stage_skin_choices()
    assert key not in _patch_skin_choices()
    assert key not in _stage_skin_choices()


def test_the_patch_face_is_title_pins_and_body(library_system, group) -> None:
    graph, card, _definition, _staged = group
    ui_node = _draw(library_system, graph, card, PATCH)
    outside = _outside_body(ui_node)

    assert len(_bodies(ui_node)) == 1
    assert _labels(outside) == [card.node.props.label or card.node.identity.label]
    pins = {
        e._props["data-pin-id"]
        for e in outside
        if "data-pin-id" in e._props and "data-pin-ghost" not in e._props
    }
    assert pins == {p.id for p in card.node.get_all_ports() if p.has_pin() and not p.is_fold}
    assert pins
    ui_node.teardown_subscriptions()


def test_the_stage_face_is_the_body_only(library_system, group) -> None:
    graph, card, _definition, _staged = group
    ui_node = _draw(library_system, graph, card, STAGE)
    outside = _outside_body(ui_node)

    assert len(_bodies(ui_node)) == 1
    assert _labels(outside) == []
    assert not [e for e in outside if "data-pin-id" in e._props]
    ui_node.teardown_subscriptions()


def test_the_body_draws_the_staged_interior(library_system, group) -> None:
    graph, card, _definition, staged = group
    ui_node = _draw(library_system, graph, card, PATCH)
    (body,) = _bodies(ui_node)

    assert [e for e in body.descendants() if e._props.get("data-hw-inset-node") == staged.node_id]
    ui_node.teardown_subscriptions()


def test_an_empty_stage_shows_the_placeholder(library_system, group) -> None:
    graph, card, _definition, staged = group
    staged.node.props.on_stage = False
    ui_node = _draw(library_system, graph, card, PATCH)
    (body,) = _bodies(ui_node)

    assert _labels(list(body.descendants())) == [_PLACEHOLDER]
    ui_node.teardown_subscriptions()


def _inset_on(graph: BaseGraph, wrapper) -> Any:
    wrapper.node.props.skin = _inset_key()
    wrapper.node.props.stage_skin = _inset_key()
    return wrapper


def test_a_node_without_an_interior_says_so(library_system, group) -> None:
    from haybale_graph_editor.skins.inset_skin import NO_INTERIOR

    graph, _card, _definition, _staged = group
    plain = _inset_on(graph, make_node(graph, _ADD))
    ui_node = _draw(library_system, graph, plain, PATCH)
    (body,) = _bodies(ui_node)

    assert _labels(list(body.descendants())) == [NO_INTERIOR]
    ui_node.teardown_subscriptions()


def test_a_graph_node_whose_interior_is_missing_says_so(library_system, group) -> None:
    from haybale_graph_editor.skins.inset_skin import NO_INTERIOR

    from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY

    graph, _card, _definition, _staged = group
    unbound = _inset_on(graph, make_node(graph, _CARD, node_data={"store": {SUBGRAPH_KEY: "gone"}}))
    ui_node = _draw(library_system, graph, unbound, PATCH)
    (body,) = _bodies(ui_node)

    assert _labels(list(body.descendants())) == [NO_INTERIOR]
    ui_node.teardown_subscriptions()


def test_a_stand_in_says_its_node_failed_to_build(library_system, group) -> None:
    from haybale_graph_editor.skins.inset_skin import FAILED_TO_BUILD

    graph, _card, _definition, _staged = group
    wrapper = graph.create_node_wrapper("haybale-testing:node:NoSuchGroup", position=(0.0, 0.0))
    assert wrapper is not None
    assert wrapper.is_stand_in
    _inset_on(graph, wrapper)
    ui_node = _draw(library_system, graph, wrapper, STAGE)
    (body,) = _bodies(ui_node)

    assert _labels(list(body.descendants())) == [FAILED_TO_BUILD]
    ui_node.teardown_subscriptions()


def test_a_collapsed_inset_has_no_body(library_system, group) -> None:
    graph, card, _definition, _staged = group
    card.node.props.collapsed = True
    ui_node = _draw(library_system, graph, card, PATCH)

    assert _bodies(ui_node) == []
    ui_node.teardown_subscriptions()


def test_redrawing_the_card_releases_the_old_interior_cards(library_system, group) -> None:
    graph, card, _definition, staged = group
    factory = library_system.injector.get(SkinFactory)
    ui_node = _draw(library_system, graph, card, PATCH)

    ui_node.refresh(ChangeReason.NODE_REDRAW_REQUESTED)

    assert len(factory._nodeid_to_factory_subscriber[staged.node_id]) == 1
    ui_node.teardown_subscriptions()
    assert staged.node_id not in factory._nodeid_to_factory_subscriber
