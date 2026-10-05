"""CALLBACK — the subscription name a listener registers under."""

from haywire.core.types import StoreStrategy, type

from .specs import STRING
from ..wires import CallbackWire


@type(
    wire_type=CallbackWire,
    label="Callback Signal",
    description="Signal for callback execution between nodes",
    color="#ff3c00",
    default=None,
    # A signal, not an editable value: clears the TextWidget it would inherit from STRING.
    widget_key=None,
    # The node may set it; only a value the node set is worth storing.
    store_strategy=StoreStrategy.NODE_SET,
)
class CALLBACK(STRING):
    """Callback signal: the name a listener subscribes under.

    It travels like a `STRING`, has no widget, and a port stores it only when its
    node set it. An absent value means no subscription: an emitter's pool drops it.
    """
