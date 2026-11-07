"""CARRIER, the base of every type whose values hold fields, and BUNDLE, which holds nothing else."""

from __future__ import annotations

from typing import Any

from haywire.barn.builtin.carrier import BundleValue, CarrierValue
from haywire.core.types import PrimitiveField, PrimitiveType, StoreStrategy
from haywire.core.types import type as type_decorator

from ..wires import DataWire

_EMPTY_DEFAULT: dict = {"value": {}}
"""The default as JSON (``@type`` refuses a value object); ``CarrierField`` builds the value."""


@type_decorator(
    wire_type=DataWire,
    label="Carrier",
    description="Any value that can hold fields, such as an image or a bundle.",
    color="#78909c",
    store_strategy=StoreStrategy.NEVER,
    default=_EMPTY_DEFAULT,
    hidden=True,
)
class CARRIER(PrimitiveType[CarrierValue]):
    """Any value that can hold named fields: an image, a depth map or a bundle.

    An inlet of this type accepts every type derived from it. To make a type a
    carrier, derive from `CARRIER`, set `element_type_cls` to a value class derived
    from `CarrierValue`, and pass `hidden=False` to `@type`. The value is never saved.

    ```python
    @type(label="Mesh", default={"value": {}}, hidden=False)
    class MESH(CARRIER):
        element_type_cls = MeshValue

        @classmethod
        def empty_value(cls):
            return MeshValue()
    ```
    """

    def __init__(self, value: Any = None, **kwargs: Any) -> None:
        super().__init__(value, **kwargs)
        self._value = _as_carrier(type(self), self._value)  # the type's default arrives as JSON

    @classmethod
    def empty_value(cls) -> CarrierValue:
        """Return the value a pin of this type holds before anything reaches it."""
        return CarrierValue()

    def to_dict(self) -> dict:
        """Return an empty description: the content is never saved."""
        return {"value": {}}

    @classmethod
    def from_dict(cls, data: dict) -> CarrierValue:
        """Return the empty value: the content never round-trips."""
        return cls.empty_value()


class CarrierField(PrimitiveField):
    """DataField for the carrier types: starts as the type's empty value."""

    def __post_init__(self) -> None:
        super().__post_init__()
        self._default = _as_carrier(self.type_cls, self._default)
        self._value = self._default

    def _set_own(self, value: Any) -> None:
        self._value = _as_carrier(self.type_cls, value)


def _as_carrier(type_cls: Any, value: Any) -> Any:
    return type_cls.empty_value() if isinstance(value, dict) else value


CARRIER.field_class = CarrierField


@type_decorator(
    label="Bundle",
    description="Several values travelling together as fields.",
    color="#546e7a",
    default=_EMPTY_DEFAULT,
    hidden=False,
)
class BUNDLE(CARRIER):
    """Several values travelling together.

    A bundle has no content of its own. Start one with **New Bundle**, add values
    with **Metadata** stamp fields, and take them out with its read fields.
    """

    element_type_cls = BundleValue

    @classmethod
    def empty_value(cls) -> BundleValue:
        """Return a bundle with no fields."""
        return BundleValue()
