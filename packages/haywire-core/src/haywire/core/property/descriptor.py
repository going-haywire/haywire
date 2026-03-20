# haywire/core/property/descriptor.py
"""
prop — reactive property descriptor.

Instance-level access reads/writes the value stored in the owning
Bag object's __dict__.  Change notifications are fired via
``Bag._on_prop_change()``.
"""

from __future__ import annotations

from typing import Any, Callable

from .base import FieldDescriptor


class prop(FieldDescriptor):
    """
    Descriptor for a reactive property on a ``Bag`` subclass.

    Class-level access returns the descriptor itself (for introspection by
    panels and registry code).  Instance-level access reads/writes the value
    stored in the owning Bag object's __dict__.
    """

    def __init__(
        self,
        default: Any,
        *,
        label: str = '',
        description: str = '',
        category: str = 'general',
        order: int = 0,
        min: Any = None,
        max: Any = None,
        choices: 'list | dict | Callable | None' = None,
        widget: 'str | None' = None,
    ) -> None:
        self._default = default
        self._type = type(default)
        self._label = label
        self._description = description
        self._category = category
        self._order = order
        self._min = min
        self._max = max
        self._choices = choices
        self._widget = widget
        self._attr_name: str = ''   # set by __set_name__

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self   # class-level access -> descriptor itself
        return obj.__dict__.get(f'_prop_{self._attr_name}', self._default)

    def __set__(self, obj: Any, value: Any) -> None:
        key = f'_prop_{self._attr_name}'
        old = obj.__dict__.get(key, self._default)
        obj.__dict__[key] = value
        if value != old:
            obj._on_prop_change(self._attr_name, value, old)
