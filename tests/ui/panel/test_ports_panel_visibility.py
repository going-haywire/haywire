"""The Ports panel's eye hides and shows a port's row on the node card."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from nicegui import Client, ui
from nicegui.page import page as page_deco

from haywire.core.access import LevelMode
from haywire.core.graph.edit_route import EditRoute

from tests.ui.panel.test_ports_panel_reorder import _FakePort, _walk

pytestmark = pytest.mark.unit


@page_deco("/_ports_panel_visibility_test")
def _noop_page() -> None:
    pass


def _render(port: _FakePort, mode: LevelMode = LevelMode.EDIT):
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel
    from haybale_graph_editor.state.edit_state import EditState

    calls: list[tuple[str, str, bool]] = []

    def set_port_hidden(node_id: str, port_id: str, hidden: bool) -> bool:
        calls.append((node_id, port_id, hidden))
        port.hidden = hidden
        return True

    editor = SimpleNamespace(set_port_hidden=set_port_hidden)
    route = EditRoute(lambda: cast(Any, editor), lambda: mode)
    ctx = SimpleNamespace(data={EditState: SimpleNamespace(active_node=None, active_route=route)})
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        anchor = ui.column()
        with anchor:
            NodePortsPanel()._render_lane(object(), [port], "inlet", "n1", None, cast(Any, ctx))
    return anchor, calls


def _eyes(anchor) -> list:
    return [e for e in _walk(anchor) if e._props.get("icon") in ("visibility", "visibility_off")]


def test_the_eye_hides_and_shows_the_port():
    port = _FakePort(id="a", label="A")
    anchor, calls = _render(port)
    (eye,) = _eyes(anchor)
    assert eye._props["icon"] == "visibility"

    for listener in eye._event_listeners.values():
        listener.handler(None)
    assert calls == [("n1", "a", True)]
    assert eye._props["icon"] == "visibility_off"


def test_a_hidden_port_shows_the_closed_eye():
    anchor, _calls = _render(_FakePort(id="a", label="A", hidden=True))
    (eye,) = _eyes(anchor)
    assert eye._props["icon"] == "visibility_off"


def test_a_promoted_port_shows_an_inert_eye():
    anchor, _calls = _render(_FakePort(id="a", label="A", promoted=True))
    assert _eyes(anchor) == []
    icons = [e for e in _walk(anchor) if getattr(e, "_props", {}).get("name") == "visibility"]
    assert len(icons) == 1
    assert "opacity-40" in icons[0]._classes


def test_the_name_carries_the_pin_style_hover_tip():
    from haywire.ui.hover_tip import TIP_ATTR, TIP_DESC_ATTR

    anchor, _calls = _render(_FakePort(id="break_loop", label="Break", description="Signal to stop loop"))
    (name,) = [e for e in _walk(anchor) if e._props.get(TIP_ATTR) == "break_loop"]
    assert name._props[TIP_DESC_ATTR] == "Signal to stop loop"
