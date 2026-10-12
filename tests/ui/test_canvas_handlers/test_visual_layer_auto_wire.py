"""Auto-wire after a mid-drag node creation always checks the wire type."""

from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers

pytestmark = pytest.mark.unit


def _port(wire_key: str):
    p = MagicMock()
    p.is_inlet.return_value = True
    p.is_outlet.return_value = False
    p.wire_key = wire_key
    return p


def _handler():
    return VisualLayerHandlers(
        graph=MagicMock(),
        editor=MagicMock(),
        skin_factory=MagicMock(),
        canvas_vue=MagicMock(),
        allows=lambda _required: True,
        context=MagicMock(),
    )


def _wrapper(ports):
    w = MagicMock()
    w.node_id = "new"
    w.node.ports = ports
    return w


def _pending(wire):
    return {"pin_dir": "outlet", "wire": wire, "data_type": "", "node_id": "src", "pin_id": "out"}


def test_an_empty_pending_wire_matches_no_port_and_falls_back_to_the_ghost_pin():
    h = _handler()
    h._try_auto_wire(_wrapper({"a": _port("w.one")}), _pending(""))
    h.editor.create_edge.assert_called_once_with("src", "out", "new", "root_in")


def test_a_matching_wire_is_wired():
    h = _handler()
    h._try_auto_wire(_wrapper({"a": _port("w.one")}), _pending("w.one"))
    h.editor.create_edge.assert_called_once_with("src", "out", "new", "a")


def test_a_pending_swinglet_is_wired_as_the_outlet_end():
    h = _handler()
    h._try_auto_wire(_wrapper({"a": _port("w.one")}), {**_pending("w.one"), "pin_dir": "swinglet"})
    h.editor.create_edge.assert_called_once_with("src", "out", "new", "a")


def test_a_pending_inlet_is_wired_as_the_inlet_end():
    h = _handler()
    outlet = _port("w.one")
    outlet.is_inlet.return_value = False
    outlet.is_outlet.return_value = True
    h._try_auto_wire(_wrapper({"a": outlet}), {**_pending("w.one"), "pin_dir": "inlet"})
    h.editor.create_edge.assert_called_once_with("new", "a", "src", "out")
