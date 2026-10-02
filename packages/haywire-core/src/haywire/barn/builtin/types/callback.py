"""CALLBACK — the subscription name a listener registers under."""

from haywire.core.types import FlowType, StoreStrategy, type

from .specs import STRING


@type(
    flow_type=FlowType.CALLBACK,
    label="Callback Signal",
    description="Signal for callback execution between nodes",
    color="#ff3c00",
    default={"value": ""},
    # A signal, not an editable value: clears the TextWidget it would inherit from STRING.
    widget_key=None,
    # The node may set it; only a value the node set is worth storing.
    store_strategy=StoreStrategy.NODE_SET,
)
class CALLBACK(STRING):
    """Callback signal: the name a listener subscribes under.

    It travels like a `STRING`, has no widget, and a port stores it only when its
    node set it. An empty name means no subscription: an emitter drops it.
    """
