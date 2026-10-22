"""A canvas tears its cards down when the page is discarded, not on every websocket drop.

NiceGUI runs a client's disconnect handlers on every drop, also one the browser
reconnects from (the page and its DOM stay). A card or widget that tore itself
down there would stay on screen deaf to every later change.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from nicegui import Client, ui

from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haybale_graph_editor.editors.graph_canvas.ui_node import UINode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.graph.types import ChangeReason
from haywire.core.node.layout import PATCH
from haywire.ui.skin.factory import SkinFactory
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.factory import WidgetFactory

from tests.conftest import edit_route, make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"


def _noop_page() -> None:
    pass


def _client() -> Client:
    return Client(cast(Any, _noop_page), request=None)


def _handler_count(client: Client) -> int:
    return len(client.disconnect_handlers) + len(client.delete_handlers)


def _drop(client: Client) -> None:
    """Run the disconnect handlers, as ``Client.handle_disconnect`` does on a websocket drop."""
    for handler in list(client.disconnect_handlers):
        client.safe_invoke(handler)


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


def _card(library_system, graph: BaseGraph, client: Client) -> UINode:
    wrapper = make_node(graph, _ADD)
    with client:
        ui_node = UINode(
            ui.element("div"),
            wrapper,
            library_system.injector.get(SkinFactory),
            edit_route(Editor(graph, library_system.get_node_factory())),
            channel=PATCH,
        )
        ui_node.refresh(ChangeReason.NODE_ADDED)
    return ui_node


def test_a_card_registers_no_client_handler(library_system, held_graph: BaseGraph) -> None:
    client = _client()
    before = _handler_count(client)

    ui_node = _card(library_system, held_graph, client)

    # Neither the card nor its widgets: a widget anchors its cleanup to its own element.
    assert ui_node.current_ui_card is not None
    assert ui_node.current_ui_card.widget_instances, "the card has widgets to check"
    assert _handler_count(client) == before
    ui_node.teardown_subscriptions()


def test_a_disconnect_leaves_the_cards_subscribed(library_system, held_graph: BaseGraph) -> None:
    client = _client()
    ui_node = _card(library_system, held_graph, client)
    factory = library_system.injector.get(SkinFactory)

    _drop(client)

    assert ui_node.wrapper.node_id in factory._nodeid_to_factory_subscriber
    ui_node.teardown_subscriptions()


def test_deleting_the_client_tears_the_canvas_cards_down() -> None:
    layer = VisualLayerHandlers.__new__(VisualLayerHandlers)
    card = MagicMock()
    layer.node_panels = {"n1": card}
    layer.edge_states = {}
    client = _client()

    layer._release_on_client_delete(client)
    client.delete()

    card.teardown_subscriptions.assert_called_once()


def test_a_widget_survives_a_disconnect(library_system, held_graph: BaseGraph) -> None:
    wrapper = make_node(held_graph, _ADD)
    port = wrapper.node.ports["value_a"]
    client = _client()
    with client:
        widget, _element = library_system.injector.get(WidgetFactory).render_widget(
            "haywire-core:widget:NumberWidget", port, wrapper.node_id
        )
    assert isinstance(widget, BaseWidget)

    _drop(client)

    assert widget._model_dispatch_cb is not None
    widget.cleanup()
