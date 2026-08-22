"""LayoutDirection side/vector tables and the invariants that keep them honest."""

import pytest

from haywire.core.types import LayoutDirection

L2R = LayoutDirection.LEFT_TO_RIGHT
R2L = LayoutDirection.RIGHT_TO_LEFT
T2B = LayoutDirection.TOP_TO_BOTTOM
B2T = LayoutDirection.BOTTOM_TO_TOP


class _FakePort:
    """Minimal stand-in — side_for/vector_for only ever call is_inlet()."""

    def __init__(self, is_inlet: bool) -> None:
        self._is_inlet = is_inlet

    def is_inlet(self) -> bool:
        return self._is_inlet


@pytest.mark.unit
class TestLayoutDirectionTables:
    @pytest.mark.parametrize(
        ("direction", "inlet_side", "outlet_side"),
        [
            (L2R, "left", "right"),
            (R2L, "right", "left"),
            (T2B, "top", "bottom"),
            (B2T, "bottom", "top"),
        ],
    )
    def test_sides(self, direction, inlet_side, outlet_side):
        assert direction.inlet_side == inlet_side
        assert direction.outlet_side == outlet_side

    @pytest.mark.parametrize(
        ("direction", "inlet_vector", "outlet_vector"),
        [
            (L2R, (-1, 0), (1, 0)),
            (R2L, (1, 0), (-1, 0)),
            (T2B, (0, -1), (0, 1)),
            (B2T, (0, 1), (0, -1)),
        ],
    )
    def test_vectors(self, direction, inlet_vector, outlet_vector):
        assert direction.inlet_vector == inlet_vector
        assert direction.outlet_vector == outlet_vector

    def test_l2r_reproduces_pre_feature_vectors(self):
        """The historical hardcoding in render_pin, preserved exactly."""
        assert L2R.inlet_vector == (-1, 0)
        assert L2R.outlet_vector == (1, 0)
        assert L2R.inlet_side == "left"
        assert L2R.outlet_side == "right"


@pytest.mark.unit
class TestLayoutDirectionInvariants:
    @pytest.mark.parametrize("direction", list(LayoutDirection))
    def test_inlet_and_outlet_never_share_a_side(self, direction):
        assert direction.inlet_side != direction.outlet_side

    @pytest.mark.parametrize("direction", list(LayoutDirection))
    def test_vectors_are_opposed(self, direction):
        ix, iy = direction.inlet_vector
        ox, oy = direction.outlet_vector
        assert (ix, iy) == (-ox, -oy)

    @pytest.mark.parametrize("direction", list(LayoutDirection))
    def test_vectors_are_unit_and_axis_aligned(self, direction):
        for vx, vy in (direction.inlet_vector, direction.outlet_vector):
            assert abs(vx) + abs(vy) == 1

    @pytest.mark.parametrize("direction", list(LayoutDirection))
    def test_side_and_vector_agree_on_axis(self, direction):
        """The one contract worth enforcing: a mismatch fails silently in the DOM."""
        horizontal_sides = {"left", "right"}
        for side, (vx, vy) in (
            (direction.inlet_side, direction.inlet_vector),
            (direction.outlet_side, direction.outlet_vector),
        ):
            side_is_horizontal = side in horizontal_sides
            vector_is_horizontal = vx != 0
            assert side_is_horizontal == vector_is_horizontal
            # left/top are the negative directions on their axis.
            assert (side in ("left", "top")) == ((vx + vy) < 0)

    @pytest.mark.parametrize(
        ("direction", "expected"),
        [(L2R, False), (R2L, False), (T2B, True), (B2T, True)],
    )
    def test_is_vertical(self, direction, expected):
        assert direction.is_vertical is expected


@pytest.mark.unit
class TestLayoutDirectionPortHelpers:
    @pytest.mark.parametrize("direction", list(LayoutDirection))
    def test_side_for_and_vector_for_follow_port_direction(self, direction):
        inlet, outlet = _FakePort(True), _FakePort(False)
        assert direction.side_for(inlet) == direction.inlet_side
        assert direction.side_for(outlet) == direction.outlet_side
        assert direction.vector_for(inlet) == direction.inlet_vector
        assert direction.vector_for(outlet) == direction.outlet_vector


@pytest.mark.unit
class TestLayoutDirectionCoerce:
    @pytest.mark.parametrize("direction", list(LayoutDirection))
    def test_round_trips_through_its_stored_value(self, direction):
        assert LayoutDirection.coerce(direction.value) is direction

    @pytest.mark.parametrize("direction", list(LayoutDirection))
    def test_accepts_an_enum_member_unchanged(self, direction):
        assert LayoutDirection.coerce(direction) is direction

    @pytest.mark.parametrize("bad", ["", "sideways", "L2R", None, 3, object()])
    def test_unknown_values_degrade_to_l2r_rather_than_raise(self, bad):
        """This runs on the render path — a stale string must not kill a card."""
        assert LayoutDirection.coerce(bad) is L2R

    def test_every_member_has_a_label(self):
        labels = [d.label for d in LayoutDirection]
        assert all(labels)
        assert len(set(labels)) == len(labels)
