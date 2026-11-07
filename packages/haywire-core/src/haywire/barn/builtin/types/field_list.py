"""FIELD_LIST: the fields a Metadata node stamps or reads, each a key and a type."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from haywire.barn.builtin import widget_keys
from haywire.core.types import IType, StoreStrategy
from haywire.core.types import type as type_decorator
from haywire.core.types.base import BaseType
from haywire.core.types.utils import serialize_element_type

from ..wires import DataWire

_KEY = re.compile(r"[a-zA-Z0-9_]+")


def is_valid_key(key: str) -> bool:
    """Return whether ``key`` can name a field: one or more of ``a-z``, ``A-Z``, ``0-9`` and ``_``."""
    return _KEY.fullmatch(key) is not None


@dataclass(frozen=True)
class FieldEntry:
    """One declared field.

    Attributes:
        key: The field's name; see ``is_valid_key``.
        recipe: The field's type, as ``serialize_element_type`` gives it. It is
            resolved when pins are built, so an entry whose library is not
            installed survives a load.
    """

    key: str
    recipe: dict[str, Any]


def _entries_from(raw: Any) -> tuple[FieldEntry, ...]:
    """Return the well-formed entries of ``raw``, first of each key only; anything else is dropped."""
    if not isinstance(raw, (list, tuple)):
        return ()
    entries: dict[str, FieldEntry] = {}
    for item in raw:
        entry = item if isinstance(item, FieldEntry) else _entry_from(item)
        if entry is not None and entry.key not in entries:
            entries[entry.key] = entry
    return tuple(entries.values())


def _entry_from(item: Any) -> FieldEntry | None:
    if not isinstance(item, dict):
        return None
    key, recipe = item.get("key"), item.get("recipe")
    if not isinstance(key, str) or not is_valid_key(key) or not isinstance(recipe, dict):
        return None
    return FieldEntry(key, recipe)


@type_decorator(
    wire_type=DataWire,
    label="Field list",
    description="Fields declared by key and type",
    color="#78909c",
    default={"entries": []},
    store_strategy=StoreStrategy.ALWAYS,
    widget_key=widget_keys.FIELD_LIST_WIDGET,
    hidden=True,
)
@dataclass(eq=True)
class FIELD_LIST(BaseType):
    """Fields declared by key and type, edited as a list in the Properties panel.

    A key holds letters, digits and `_`, and appears once. Every change returns a
    new list; write it back to the setting.

    ```python
    class fields(NodeSettings):
        stamp = setting[FIELD_LIST](FIELD_LIST, label="Stamp", promotable=Promotable.NONE)

    self.fields.stamp = self.fields.stamp.with_added("camera_timestamp", FLOAT)
    ```
    """

    entries: tuple[FieldEntry, ...] = ()

    def __init__(self, **kwargs: Any) -> None:
        """Build a list from its entries, dropping malformed and repeated ones; never raises on them."""
        self.entries = _entries_from(kwargs.get("entries"))

    def to_dict(self) -> dict:
        return {"entries": [{"key": e.key, "recipe": e.recipe} for e in self.entries]}

    @classmethod
    def from_dict(cls, data: dict) -> FIELD_LIST:
        """Rebuild from stored JSON, tolerating anything a hand edit left."""
        return cls(entries=data.get("entries")) if isinstance(data, dict) else cls()

    def with_added(self, key: str, type_cls: type[IType]) -> FIELD_LIST:
        """Return this list with a field added at the end.

        Raises:
            ValueError: ``key`` is not valid, or is already in the list.
        """
        if not is_valid_key(key):
            raise ValueError(f"A key holds only letters, digits and _, got {key!r}")
        if any(e.key == key for e in self.entries):
            raise ValueError(f"Field {key!r} is already in the list")
        return FIELD_LIST(entries=(*self.entries, FieldEntry(key, dict(serialize_element_type(type_cls)))))

    def without(self, key: str) -> FIELD_LIST:
        """Return this list without ``key``; unchanged if it is absent."""
        return FIELD_LIST(entries=[e for e in self.entries if e.key != key])
