# tests/core/settings/test_promotable_eligibility.py
"""
promotable= eligibility:

- Promotable Flag enum semantics and the setting() kwarg (this task)
- eligible_promotion_directions() matrix, promote_setting guard, and the
  promote guard (added in Task 3 of the merged plan)
- the promote menu consumes the same helper (tests/ui/menu/test_promote_demote_menu.py)
"""

# Per CLAUDE.md test trap: import editor before other haywire modules.
import haywire.core.graph.editor  # noqa: F401

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.settings import Promotable, setting


@pytest.mark.unit
class TestPromotableEnum:
    def test_all_is_inlet_or_outlet(self):
        assert Promotable.ALL == Promotable.INLET | Promotable.OUTLET

    def test_none_contains_nothing(self):
        assert Promotable.INLET not in Promotable.NONE
        assert Promotable.OUTLET not in Promotable.NONE

    def test_membership(self):
        assert Promotable.INLET in Promotable.ALL
        assert Promotable.OUTLET in Promotable.ALL
        assert Promotable.OUTLET not in Promotable.INLET


@pytest.mark.unit
class TestPromotableKwarg:
    def test_default_is_all(self):
        desc = setting(0.5, type_=FLOAT)
        assert desc._promotable is Promotable.ALL

    def test_kwarg_is_stored(self):
        desc = setting(0.5, type_=FLOAT, promotable=Promotable.NONE)
        assert desc._promotable is Promotable.NONE

    def test_single_direction_is_stored(self):
        desc = setting(0.5, type_=FLOAT, promotable=Promotable.OUTLET)
        assert desc._promotable is Promotable.OUTLET
