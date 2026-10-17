"""``GraphCanvasManager.center_on_node`` pans the canvas to a node's card; a reveal uses it."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_canvas.graph_canvas_manager import GraphCanvasManager


class TestCentreOnNode:
    """``center_on_node`` pans this canvas to the node's centre, in the canvas's own channel."""

    def _manager(self, props: Any, *, shown: bool = True, channel: Any = None) -> Any:
        from haywire.core.node.layout import PATCH

        manager: Any = object.__new__(GraphCanvasManager)
        manager.channel = channel or PATCH
        wrapper = SimpleNamespace(node=SimpleNamespace(props=props))
        manager.graph = SimpleNamespace(get_node_wrapper=lambda node_id: wrapper if shown else None)
        manager.visual_layer = SimpleNamespace(shows_node=lambda node_id: shown)
        manager.zoom_container = MagicMock()
        return manager

    @pytest.mark.unit
    def test_it_pans_to_the_middle_of_the_card(self):
        props = SimpleNamespace(posX=100.0, posY=40.0, width=200.0, height=60.0)
        manager = self._manager(props)

        manager.center_on_node("n1")

        manager.zoom_container.center_on.assert_called_once_with(200.0, 70.0)

    @pytest.mark.unit
    def test_a_stage_canvas_adds_its_origin(self):
        from haywire.core.node.layout import STAGE

        props = SimpleNamespace(**{STAGE.x: 10.0, STAGE.y: 20.0, STAGE.width: 40.0, STAGE.height: 20.0})
        manager = self._manager(props, channel=STAGE)

        manager.center_on_node("n1")

        manager.zoom_container.center_on.assert_called_once_with(STAGE.origin + 30.0, STAGE.origin + 30.0)

    @pytest.mark.unit
    def test_a_node_this_canvas_does_not_show_leaves_the_viewport(self):
        manager = self._manager(SimpleNamespace(), shown=False)

        manager.center_on_node("n1")

        manager.zoom_container.center_on.assert_not_called()
