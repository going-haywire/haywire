"""Test-only wire types."""

from haywire.core.types import WireRole, WireType


class TestVisualWire(WireType):
    """A drawn-only wire for tests: saved and drawn, never executed."""

    role = WireRole.VISUAL
    propagation = ()
    pin_kind = "test_visual"
