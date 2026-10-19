"""InsetView: a Subgraph's staged nodes, each drawn by its own card at its stage position."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest
from nicegui import Client, ui

from haybale_graph_editor.editors.graph_canvas.inset_view import InsetView
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.ui.skin.factory import SkinFactory

from tests.conftest import edit_route, make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"


def _noop_page() -> None:
    pass


@pytest.fixture
def interior(library_system) -> Iterator[tuple[BaseGraph, SubgraphDefinition, Any, Any]]:
    """A host graph with a Subgraph of two adders, one of them on stage at (30, 40)."""
    graph = BaseGraph(
        filestem="host", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    definition = graph.add_subgraph(SubgraphDefinition(key="sg", label="Group"))
    staged = make_node(definition, _ADD)
    staged.node.props.on_stage = True
    staged.node.props.stage_x = 30.0
    staged.node.props.stage_y = 40.0
    hidden = make_node(definition, _ADD)
    yield graph, definition, staged, hidden
    graph._validation.clear()
    graph.cleanup()


@pytest.fixture
def built(library_system, interior):
    graph, definition, staged, hidden = interior
    route = edit_route(Editor(graph, library_system.get_node_factory()))
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        body = ui.element("div")
        view = InsetView(body, definition, library_system.injector.get(SkinFactory), route)
    yield view, body, staged, hidden
    view.cleanup()


def test_only_staged_interior_nodes_get_a_card(built) -> None:
    view, _body, staged, _hidden = built

    assert set(view.cards) == {staged.node_id}


def test_a_card_sits_at_its_stage_position(built) -> None:
    view, _body, staged, _hidden = built

    container = view.cards[staged.node_id].container

    assert container._style["left"] == "30.0px"
    assert container._style["top"] == "40.0px"


def test_interior_cards_carry_no_node_id_attribute(built) -> None:
    view, body, staged, _hidden = built
    containers = [e for e in body.descendants() if e._props.get("data-hw-inset-node") == staged.node_id]

    assert containers == [view.cards[staged.node_id].container]
    assert "data-node-id" not in containers[0]._props


def test_a_redraw_releases_the_interior_cards(built, library_system) -> None:
    view, _body, staged, _hidden = built
    factory = library_system.injector.get(SkinFactory)
    assert staged.node_id in factory._nodeid_to_factory_subscriber

    view.cleanup()

    assert staged.node_id not in factory._nodeid_to_factory_subscriber


def test_no_definition_builds_nothing(library_system, interior) -> None:
    graph = interior[0]
    route = edit_route(Editor(graph, library_system.get_node_factory()))
    with Client(cast(Any, _noop_page), request=None):
        view = InsetView(ui.element("div"), None, library_system.injector.get(SkinFactory), route)

    assert view.cards == {}
