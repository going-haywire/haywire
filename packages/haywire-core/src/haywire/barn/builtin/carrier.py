"""Values that can carry named fields; see ``CarrierValue``."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from haywire.core.types import IType

_NO_FIELDS: Mapping[str, Stamp] = MappingProxyType({})


@dataclass(frozen=True)
class Stamp:
    """One field on a carrier.

    Attributes:
        value: The stamped value, treated as immutable.
        type_key: Registry key of the type the value was stamped as.
    """

    value: Any
    type_key: str


class CarrierValue:
    """A value that can hold named fields, which travel with it and are never saved.

    Stamping returns a new carrier, so the original and any other branch of the
    graph never see the field. Subclasses declare ``__slots__`` and call
    ``super().__init__()``.

    Example::

        stamped = image.stamped("camera_timestamp", 1.5, FLOAT)
        stamped.fields["camera_timestamp"].value  # 1.5
        "camera_timestamp" in image.fields        # False

        # Drop one field, keep the rest
        rest = {k: v for k, v in stamped.fields.items() if k != "camera_timestamp"}
        cleared = stamped.with_fields(rest)
    """

    __slots__ = ("_fields",)

    def __init__(self) -> None:
        """Start with no fields."""
        self._fields: Mapping[str, Stamp] = _NO_FIELDS

    @property
    def fields(self) -> Mapping[str, Stamp]:
        """The carried fields by key, read-only."""
        return self._fields

    def with_fields(self, fields: Mapping[str, Stamp]) -> Self:
        """Return a copy of this value holding exactly ``fields``; content is shared, not copied."""
        out = copy.copy(self)
        out._fields = MappingProxyType(dict(fields))
        return out

    def stamped(self, key: str, value: Any, type_cls: type[IType]) -> Self:
        """Return a copy of this value with ``key`` set to ``value``, recorded as ``type_cls``."""
        return self.with_fields({**self._fields, key: Stamp(value, type_cls.class_identity.registry_key)})

    def describe(self) -> dict[str, str]:
        """Return read-only facts that are not fields, for Metadata Info; empty by default."""
        return {}


class BundleValue(CarrierValue):
    """A carrier with no content of its own, for values that travel together."""

    __slots__ = ()
