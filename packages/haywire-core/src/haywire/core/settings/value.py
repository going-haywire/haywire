# haywire/core/settings/value.py
"""
SettingValue - stores mode and value for a field.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

from .enums import SettingMode

T = TypeVar("T")


@dataclass
class SettingValue(Generic[T]):
    """
    A field's stored state (mode + optional value).

    This is what gets serialized for both global and local settings.
    """

    mode: SettingMode = SettingMode.INHERIT
    value: T | None = None

    def is_inherit(self) -> bool:
        """Check if this field inherits from parent."""
        return self.mode == SettingMode.INHERIT

    def is_explicit(self) -> bool:
        """Check if this field has an explicit value."""
        return self.mode == SettingMode.EXPLICIT

    def is_override(self) -> bool:
        """Check if this field forces value on children."""
        return self.mode == SettingMode.OVERRIDE

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {"mode": self.mode.name, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict) -> "SettingValue":
        """Deserialize from storage."""
        return cls(mode=SettingMode[data.get("mode", "INHERIT")], value=data.get("value"))

    def __repr__(self) -> str:
        if self.mode == SettingMode.INHERIT:
            return "SettingValue(INHERIT)"
        return f"SettingValue({self.mode.name}, {self.value!r})"
