# tests/core/settings/test_promotable_eligibility.py
"""
promotable= eligibility:

- Promotable Flag enum semantics and the setting() kwarg (this task)
- eligible_promotion_directions() matrix, promote_setting guard, and the
  promote guard (added in Task 3 of the merged plan)
- the Setting-row menu consumes the same helper (tests/ui/panel/test_promoted_row_state.py)
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


@pytest.mark.unit
class TestEligibleDirections:
    """The eligibility matrix: declared promotable= ∩ structural read_only rule."""

    def _dirs(self, **kwargs):
        from haywire.core.node.promotion import eligible_promotion_directions

        return eligible_promotion_directions(setting(0.5, type_=FLOAT, **kwargs))

    def test_default_plain_field_both_directions(self):
        from haywire.core.types.enums import PortType

        assert self._dirs() == (PortType.INLET, PortType.OUTLET)

    def test_none_yields_empty(self):
        assert self._dirs(promotable=Promotable.NONE) == ()

    def test_inlet_only(self):
        from haywire.core.types.enums import PortType

        assert self._dirs(promotable=Promotable.INLET) == (PortType.INLET,)

    def test_outlet_only(self):
        from haywire.core.types.enums import PortType

        assert self._dirs(promotable=Promotable.OUTLET) == (PortType.OUTLET,)

    def test_read_only_intersects_to_outlet(self):
        from haywire.core.types.enums import PortType

        assert self._dirs(read_only=True) == (PortType.OUTLET,)

    def test_read_only_plus_inlet_only_intersects_to_empty(self):
        assert self._dirs(read_only=True, promotable=Promotable.INLET) == ()


@pytest.mark.integration
class TestPromoteGuard:
    """promote_setting raises for ineligible promotions (interactive OR load-time)."""

    def test_promote_none_field_raises(self, make_node_with_setting):
        from haywire.core.node.promotion import promote_setting
        from haywire.core.types.enums import PortType

        node = make_node_with_setting(accessor="filter", field="threshold")
        # Stamp this instance's descriptor NONE (fresh bag class per fixture — no leak).
        type(node.filter).__dict__["threshold"]._promotable = Promotable.NONE
        for direction in (PortType.INLET, PortType.OUTLET):
            with pytest.raises(ValueError, match="cannot be promoted"):
                promote_setting(node, "filter", "threshold", direction)
        pid = type(node.filter).__dict__["threshold"].storage_key
        assert pid not in node.ports

    def test_promote_outlet_only_field_to_inlet_raises(self, make_node_with_setting):
        from haywire.core.node.promotion import promote_setting
        from haywire.core.types.enums import PortType

        node = make_node_with_setting(accessor="filter", field="threshold")
        type(node.filter).__dict__["threshold"]._promotable = Promotable.OUTLET
        with pytest.raises(ValueError, match="cannot be promoted"):
            promote_setting(node, "filter", "threshold", PortType.INLET)
        promote_setting(node, "filter", "threshold", PortType.OUTLET)  # allowed
