"""Where a computed edge draws its arrow head: a fact its wire type declares."""

import pytest

from haywire.barn.builtin.wires import CallbackWire, ControlWire, DataWire
from haywire.core.types import ArrowAt

pytestmark = pytest.mark.unit


def test_a_wire_type_draws_its_computed_head_at_the_inlet_by_default():
    assert DataWire.arrow_at is ArrowAt.INLET
    assert ControlWire.arrow_at is ArrowAt.INLET


def test_a_callback_edge_draws_its_head_at_the_outlet():
    assert CallbackWire.arrow_at is ArrowAt.OUTLET


def test_the_values_are_the_canvas_class_suffixes():
    assert [member.value for member in ArrowAt] == ["inlet", "outlet", "none"]
