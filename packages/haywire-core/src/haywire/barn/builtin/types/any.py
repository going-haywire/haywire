"""ANY — a port whose type is decided by the first thing connected to it."""

from typing import Any as AnyValue

from haywire.core.types import FlowType, PortType, PrimitiveType, StoreStrategy, type


@type(
    flow_type=FlowType.DATA,
    label="Any",
    description="Undecided until connected; the node retypes the port from the other end",
    color="#9e9e9e",
    default={"value": None},
    # A placeholder holds nothing worth saving, and a PrimitiveType cannot
    # represent absence — constructing one to serialize would raise.
    store_strategy=StoreStrategy.NEVER,
)
class ANY(PrimitiveType[object]):
    """A placeholder pin that takes its type from the first edge drawn to it.

    An `ANY` pin connects to anything, and connecting is the point: the node
    reads the type from the other end and replaces the pin with a real one of
    that type. Use it where the node cannot know the type in advance — a group
    input that declares its interface when the user wires it, or a node that
    grows a fresh slot each time one is filled.

    The node does the retyping; the type only makes the connection possible.
    Give the port an `on_connect` handler and rebuild the port inside `rejig`:

    ```python
    def init(self):
        self.add(ANY.as_inlet("in_0", on_connect="_resolve"))

    def _resolve(self, port, edge_wrapper):
        incoming = edge_wrapper._outlet_port.stored_type
        if incoming._is_any:
            return  # the other end is undecided too — nothing to adopt
        with self.rejig(include=[port.id]):
            self.add(incoming.as_inlet(port.id, on_connect="_resolve"))
    ```

    The edge survives the swap and rebuilds against the new type on the next
    validation pass. A handler that declines to retype leaves the pin `ANY` and
    the edge passing values through untouched, which is how a node restricts
    itself to the types it actually accepts.

    An edge between two `ANY` pins is valid and does nothing: neither end has a
    type to give. Both resolve once either is connected to something concrete.

    Holds no value of its own and renders no widget. Cannot be a config port —
    a config never connects, so an `ANY` config could never resolve.
    """

    _is_any = True

    def __init__(self, value: AnyValue = None, **kwargs: AnyValue) -> None:
        """Wrap *value*, where ``None`` means "not decided yet".

        ``PrimitiveType`` rejects ``None``, which a placeholder must be able to
        hold: an unresolved pin has no value, and anything that constructs one
        to inspect it — serialization included — would otherwise raise.
        """
        self._value = value if value is not None else kwargs.get("value")

    def to_dict(self) -> dict:
        return {"value": None}

    @classmethod
    def from_dict(cls, data: dict) -> AnyValue:
        return None

    @classmethod
    def _validate_port_type(cls, port_type: PortType) -> None:
        """Reject CONFIG.

        Raises:
            ValueError: If *port_type* is ``PortType.CONFIG``.
        """
        if port_type == PortType.CONFIG:
            raise ValueError(
                "ANY cannot be a config port: a config port has no pin, so it "
                "never connects and could never resolve to a real type."
            )
