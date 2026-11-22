from __future__ import annotations

from haywire.api import DataWire, PrimitiveType, type

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
    """Raw binary data, saved in a graph as base64 text."""

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
    label="Untyped List",
    description="Ordered collection of values of any type",
    color="#e91e63",
    default={"value": []},
)
class LIST(PrimitiveType[list]):
    """An ordered list whose items may be of any type and are not checked.

    Use `ARRAY[T]` for a list of one item type: the port knows the item type, so pins and
    adapters follow it. `LIST` is for values whose items have no single type.
    """

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
    """Key-value pairs of any types, passed on as a plain `dict`."""

    def to_dict(self) -> dict:
        return {"value": dict(self._value)}

    @classmethod
    def from_dict(cls, data: dict) -> dict:
        return dict(data.get("value", {}))
