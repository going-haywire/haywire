"""The wire types the framework ships: data, control and callback.

A value type travels on one of these unless its library defines its own wire
type (see ``haywire.core.types.wire``). Import them from this module; types in
the builtin library import them relatively.
"""

from haywire.core.types.enums import Propagation
from haywire.core.types.wire import ArrowAt, WireRole, WireType


class DataWire(WireType):
    """Values, pulled by assembly for the node that needs them."""

    role = WireRole.DEPENDENT
    propagation = (Propagation.EAGER, Propagation.LAZY)
    pin_kind = "data"


class ControlWire(WireType):
    """Execution order, walked forward by the VM."""

    role = WireRole.SEQUENCE
    propagation = (Propagation.EAGER, Propagation.LAZY)
    pin_kind = "control"


class CallbackWire(WireType):
    """Subscriptions, which take effect as soon as they are written.

    A computed head points at the outlet: the listener the callback returns to.
    """

    role = WireRole.IMMEDIATE
    propagation = ()
    pin_kind = "callback"
    arrow_at = ArrowAt.OUTLET
