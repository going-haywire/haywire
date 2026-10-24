"""The Properties inspectors poll on their subject alone, in every level mode.

Below edit a tab still shows, read-only: its writers are greyed by the panel
gate (ADR 0060), and the route refuses what gets through.
"""

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


def _ctx(route: EditRoute | None, *, selected: bool = True) -> Any:
    """A session context with ``route`` on screen and a graph, node and edge selected (or none)."""
    subject = object() if selected else None
    state = SimpleNamespace(
        active_graph=subject, active_node=subject, active_edge=subject, active_route=route
    )
    return SimpleNamespace(data={EditState: state})


def _route_in(mode: LevelMode) -> EditRoute:
    return EditRoute(lambda: None, lambda: mode)  # type: ignore[arg-type,return-value]


@pytest.mark.parametrize("mode", [LevelMode.VIEW, LevelMode.OPERATE, LevelMode.EDIT])
def test_graph_inspectors_show_in_every_mode(mode: LevelMode):
    ctx = _ctx(_route_in(mode))

    assert [cls.poll(ctx) for cls in _GRAPH_INSPECTORS] == [True] * 5


@pytest.mark.parametrize("mode", [LevelMode.VIEW, LevelMode.OPERATE, LevelMode.EDIT])
def test_graph_inspectors_hide_without_their_subject(mode: LevelMode):
    ctx = _ctx(_route_in(mode), selected=False)

    assert [cls.poll(ctx) for cls in _GRAPH_INSPECTORS] == [False] * 5


def test_the_execution_tab_stays_in_view():
    assert ExecutionInspector.poll(_ctx(_route_in(LevelMode.VIEW))) is True
