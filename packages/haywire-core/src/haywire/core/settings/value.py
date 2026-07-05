# haywire/core/settings/value.py
"""
SettingValue — a tier's stored opinion: either set (carries a value) or unset.

A tier value is simply set-or-unset; resolution is highest-priority-set-wins.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class SettingValue(Generic[T]):
    """A tier's stored state: ``is_set`` plus an optional ``value``.

    Construct via :meth:`unset` / :meth:`of` rather than the raw fields.
    """

    is_set: bool = False
    value: T | None = None

    @classmethod
    def unset(cls) -> "SettingValue[T]":
        """A tier with no opinion — defers to the next tier in priority order."""
        return cls(is_set=False, value=None)

    @classmethod
    def of(cls, value: T) -> "SettingValue[T]":
        """A tier holding *value* — eligible to win resolution."""
        return cls(is_set=True, value=value)

    def to_dict(self) -> dict:
        """Serialize for storage. Unset values serialize to ``{}``."""
        return {"value": self.value} if self.is_set else {}

    @classmethod
    def from_dict(cls, data: dict) -> "SettingValue":
        """Deserialize from storage."""
        if "value" in data:
            return cls.of(data["value"])
        return cls.unset()

    def __repr__(self) -> str:
        if not self.is_set:
            return "SettingValue(unset)"
        return f"SettingValue({self.value!r})"
