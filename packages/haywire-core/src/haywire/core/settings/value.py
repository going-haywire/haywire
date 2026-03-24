# haywire/core/settings/value.py
"""
SettingValue - stores mode and value for a setting.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

from .enums import SettingMode

T = TypeVar("T")


@dataclass
class SettingValue(Generic[T]):
    """
    A setting's stored state (mode + optional value).

    This is what gets serialized for both global and local settings.
    """

    mode: SettingMode = SettingMode.AUTO
    value: T | None = None

    def is_auto(self) -> bool:
        """Check if this setting inherits from parent."""
        return self.mode == SettingMode.AUTO

    def is_set(self) -> bool:
        """Check if this setting has an explicit value."""
        return self.mode == SettingMode.SET

    def is_override(self) -> bool:
        """Check if this setting forces value on children."""
        return self.mode == SettingMode.OVERRIDE

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {"mode": self.mode.name, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict) -> "SettingValue":
        """Deserialize from storage."""
        return cls(mode=SettingMode[data.get("mode", "AUTO")], value=data.get("value"))

    def __repr__(self) -> str:
        if self.mode == SettingMode.AUTO:
            return "SettingValue(AUTO)"
        return f"SettingValue({self.mode.name}, {self.value!r})"
