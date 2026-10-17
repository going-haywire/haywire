"""The writable Properties inspectors poll true only while the level on screen is in mode edit."""

from types import SimpleNamespace
from typing import Any

import pytest

from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.surfaces.edge import EdgeInspector
from haybale_graph_editor.surfaces.graph import GraphInspector
from haybale_graph_editor.surfaces.node import NodeInspector, SettingsInspector
from haybale_graph_editor.surfaces.ports import PortInspector
from haywire.barn.builtin.surfaces import ExecutionInspector
from haywire.core.access import LevelMode
from haywire.core.graph.edit_route import EditRoute

pytestmark = pytest.mark.unit

_GRAPH_INSPECTORS = [GraphInspector, NodeInspector, SettingsInspector, PortInspector, EdgeInspector]


def _ctx(route: EditRoute | None) -> Any:
    """A session context with a graph, node and edge selected, and ``route`` on screen."""
    state = SimpleNamespace(
        active_graph=object(), active_node=object(), active_edge=object(), active_route=route
    )
    return SimpleNamespace(data={EditState: state})


def _route_in(mode: LevelMode) -> EditRoute:
    return EditRoute(lambda: None, lambda: mode)  # type: ignore[arg-type,return-value]


@pytest.mark.parametrize("mode", [LevelMode.VIEW, LevelMode.OPERATE])
def test_graph_inspectors_hide_below_edit(mode: LevelMode):
    ctx = _ctx(_route_in(mode))

    assert [cls.poll(ctx) for cls in _GRAPH_INSPECTORS] == [False] * 5


def test_graph_inspectors_show_in_edit():
    ctx = _ctx(_route_in(LevelMode.EDIT))

    assert [cls.poll(ctx) for cls in _GRAPH_INSPECTORS] == [True] * 5


def test_no_route_shows_no_graph_inspector():
    ctx = _ctx(None)

    assert [cls.poll(ctx) for cls in _GRAPH_INSPECTORS] == [False] * 5


def test_the_execution_tab_stays_in_view():
    assert ExecutionInspector.poll(_ctx(_route_in(LevelMode.VIEW))) is True
