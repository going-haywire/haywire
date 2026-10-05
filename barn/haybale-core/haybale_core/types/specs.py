from haywire.core.types import type, PrimitiveType
from haywire.barn.builtin.wires import DataWire

# ============================================================================
# Binary Type
# ============================================================================


@type(
    wire_type=DataWire,
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
    wire_type=DataWire,
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
    wire_type=DataWire,
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
