"""The level mode a session gets from its tier and the lock, and the edit check built on it."""

from types import SimpleNamespace
from typing import Any

import pytest

from haybale_graph_editor.access import can_edit_graph, level_mode
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.access import AccessTier, LevelMode
from haywire.core.graph.edit_route import EditRoute

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("tier", "locked", "expected"),
    [
        (AccessTier.VIEW, False, LevelMode.VIEW),
        (AccessTier.VIEW, True, LevelMode.VIEW),
        (AccessTier.OPERATE, False, LevelMode.OPERATE),
        (AccessTier.OPERATE, True, LevelMode.OPERATE),
        (AccessTier.EDIT, False, LevelMode.EDIT),
        (AccessTier.EDIT, True, LevelMode.OPERATE),
        (AccessTier.ADMIN, False, LevelMode.EDIT),
        (AccessTier.ADMIN, True, LevelMode.OPERATE),
    ],
)
def test_level_mode_table(tier: AccessTier, locked: bool, expected: LevelMode):
    assert level_mode(tier.satisfies, locked) is expected


def _ctx(route: EditRoute | None) -> Any:
    return SimpleNamespace(data={EditState: SimpleNamespace(active_route=route)})


def test_can_edit_graph_follows_the_active_route():
    def route_in(level: LevelMode) -> EditRoute:
        return EditRoute(lambda: None, lambda: level)  # type: ignore[arg-type,return-value]

    assert can_edit_graph(_ctx(None)) is False
    assert can_edit_graph(_ctx(route_in(LevelMode.OPERATE))) is False
    assert can_edit_graph(_ctx(route_in(LevelMode.VIEW))) is False
    assert can_edit_graph(_ctx(route_in(LevelMode.EDIT))) is True
