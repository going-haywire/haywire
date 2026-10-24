"""LevelMode: the per-level mode a session edits in, ordered view < operate < edit."""

import pytest

from haywire.core.access import LevelMode, required_mode

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


@pytest.mark.parametrize("minimum", list(LevelMode))
def test_required_mode_of_an_operable_target_is_its_minimum(minimum):
    assert required_mode(minimum, True) is minimum


@pytest.mark.parametrize("minimum", list(LevelMode))
def test_required_mode_of_a_non_operable_target_is_edit(minimum):
    assert required_mode(minimum, False) is LevelMode.EDIT
