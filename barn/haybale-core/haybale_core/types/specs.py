from haywire.core.types import type, FlowType, PrimitiveType, StoreStrategy

from haywire.barn.builtin.types import STRING


# ============================================================================
# Group Type
# ============================================================================


@type(
    flow_type=FlowType.DATA,
    label="Group",
    description="Inlet group",
    color="#ebff0f",
    widget_key="haywire-core:widget:SwitchWidget",
    default={"value": False},
)
class GROUP(PrimitiveType[bool]):
    """Group data type"""

    def to_dict(self) -> dict:
        return {"value": bool(self._value)}

    @classmethod
    def from_dict(cls, data: dict) -> bool:
        return bool(data.get("value", False))


# ============================================================================
# Binary Type
# ============================================================================


@type(
    flow_type=FlowType.DATA,
    label="Bytes",
    description="Binary data",
    color="#9e9e9e",
    default={"value": b""},
)
class BYTES(PrimitiveType[bytes]):
    """Bytes data type"""

    def to_dict(self) -> dict:
        import base64

        return {"value": base64.b64encode(self._value).decode("ascii")}

    @classmethod
    def from_dict(cls, data: dict) -> bytes:
        import base64

        return base64.b64decode(data.get("value", ""))


# ============================================================================
# Collection Types
# ============================================================================


@type(
    flow_type=FlowType.DATA,
    label="List",
    description="Ordered collection",
    color="#e91e63",
    default={"value": []},
)
class LIST(PrimitiveType[list]):
    """List data type"""

    def to_dict(self) -> dict:
        return {"value": list(self._value)}

    @classmethod
    def from_dict(cls, data: dict) -> list:
        return list(data.get("value", []))


@type(
    flow_type=FlowType.DATA,
    label="Dictionary",
    description="Key-value pairs",
    color="#9c27b0",
    default={"value": {}},
)
class DICT(PrimitiveType[dict]):
    """Dictionary data type"""

    def to_dict(self) -> dict:
        return {"value": dict(self._value)}

    @classmethod
    def from_dict(cls, data: dict) -> dict:
        return dict(data.get("value", {}))


# ============================================================================
# Exec Types
# ============================================================================


@type(
    flow_type=FlowType.CONTROL,
    label="Execution Signal",
    description="Signal for controlling execution flow between nodes",
    color="#004cff",
    default={"value": {}},
    store_strategy=StoreStrategy.NEVER,
)
class EXEC(PrimitiveType[dict]):
    """Execution signal carrying an optional ``dict`` payload."""

    @classmethod
    def create_default(cls) -> "EXEC":
        return cls({})


# ============================================================================
# Callback Types
# ============================================================================


@type(
    flow_type=FlowType.CALLBACK,
    label="Callback Signal",
    description="Signal for callback execution between nodes",
    color="#ff3c00",
    default={},
    # CALLBACK inherits STRING's payload but is a control-flow signal, not an
    # editable value — it must NOT inherit STRING's TextWidget. A widget_key here
    # also flips has_widget=True in StoreStrategy.should_store, which would try to
    # serialize the signal's (None) field and crash. Keep it widget-less.
    widget_key=None,
)
class CALLBACK(STRING):
    """
    callback signal type - represents callback flow
    Inherits from STRING for payload compatibility.
    """
