"""A canvas keeps its cards in graph order in the DOM, so equal-z cards paint as ``stacking_order`` says.

Cards sharing a z-index paint in DOM order; the model breaks the tie by graph order. A card
mounted later (a node put on stage) must therefore land at its graph position, not at the end.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from nicegui import Client

from haybale_graph_editor.editors.graph_canvas.handlers import visual_layer as vl_module
from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haywire.core.node.layout import STAGE
from haywire.ui.components.graph.canvas import GraphCanvasVue

from tests.conftest import edit_route

pytestmark = pytest.mark.unit


def _noop_page() -> None:
    pass


class _StubUINode:
    def __init__(self, container, wrapper, *_args, **_kwargs) -> None:
        self.container = container

    def register_sync_event_emitter(self, _emit) -> None:
        pass

    def refresh(self, _reason) -> None:
        pass


def _node(node_id: str) -> Any:
    return SimpleNamespace(node_id=node_id)


def test_a_card_mounted_later_lands_at_its_graph_position(monkeypatch):
    monkeypatch.setattr(vl_module, "UINode", _StubUINode)
    graph = MagicMock()
    graph.node_wrappers = {"a": MagicMock(), "b": MagicMock(), "c": MagicMock()}
    graph.get_node_wrapper.side_effect = lambda nid: graph.node_wrappers.get(nid)
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        canvas = GraphCanvasVue(stage=True)
        layer = VisualLayerHandlers(
            graph=graph,
            route=edit_route(MagicMock()),
            skin_factory=MagicMock(),
            canvas_vue=canvas,
            channel=STAGE,
        )
        layer.add_node_visual(_node("a"))
        layer.add_node_visual(_node("c"))

        layer.add_node_visual(_node("b"))  # b joins the stage after a and c

        cards = [child.props.get("data-node-id") for child in canvas.default_slot.children]
        assert [c for c in cards if c] == ["a", "b", "c"]
