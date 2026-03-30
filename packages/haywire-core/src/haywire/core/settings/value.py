# haywire/core/settings/value.py
"""
FieldValue - stores mode and value for a field.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

from .enums import FieldMode

T = TypeVar("T")


@dataclass
class FieldValue(Generic[T]):
    """
    A field's stored state (mode + optional value).

    This is what gets serialized for both global and local settings.
    """

    mode: FieldMode = FieldMode.INHERIT
    value: T | None = None

    def is_inherit(self) -> bool:
        """Check if this field inherits from parent."""
        return self.mode == FieldMode.INHERIT

    def is_explicit(self) -> bool:
        """Check if this field has an explicit value."""
        return self.mode == FieldMode.EXPLICIT

    def is_override(self) -> bool:
        """Check if this field forces value on children."""
        return self.mode == FieldMode.OVERRIDE

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {"mode": self.mode.name, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict) -> "FieldValue":
        """Deserialize from storage."""
        return cls(mode=FieldMode[data.get("mode", "INHERIT")], value=data.get("value"))

    def __repr__(self) -> str:
        if self.mode == FieldMode.INHERIT:
            return "FieldValue(INHERIT)"
        return f"FieldValue({self.mode.name}, {self.value!r})"
