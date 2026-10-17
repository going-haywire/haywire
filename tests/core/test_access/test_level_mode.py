"""LevelMode: the per-level mode a session edits in, ordered view < operate < edit."""

import pytest

from haywire.core.access import LevelMode

pytestmark = pytest.mark.unit


def test_wire_values():
    assert LevelMode.OPERATE == "operate"
    assert LevelMode.VIEW == "view"
    assert LevelMode.EDIT == "edit"


def test_ranks_order():
    assert LevelMode.VIEW.rank < LevelMode.OPERATE.rank < LevelMode.EDIT.rank


@pytest.mark.parametrize("required", list(LevelMode))
@pytest.mark.parametrize("mode", list(LevelMode))
def test_satisfies_matrix(mode: LevelMode, required: LevelMode):
    assert mode.satisfies(required) is (mode.rank >= required.rank)
