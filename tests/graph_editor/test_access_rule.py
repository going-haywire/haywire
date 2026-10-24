"""The level mode a session gets from its tier and the lock."""

import pytest

from haybale_graph_editor.access import level_mode
from haywire.core.access import AccessTier, LevelMode

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
