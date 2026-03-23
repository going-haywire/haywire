# haywire/core/settings/descriptors.py
"""
SettingDescriptor and setting() — used by GlobalSettings and LibrarySettings
to define fields for the GlobalSettingsRegistry TOML resolution system.

Node-local settings use prop() on Bag subclasses (haywire.core.property).
The mirrors= and read_only= params on prop() replace the old shadow()/watch().
"""

from __future__ import annotations

from typing import Any, Callable

from haywire.core.property.base import FieldDescriptor


class SettingDescriptor(FieldDescriptor):
    """
    Descriptor for a field on a GlobalSettings or LibrarySettings schema class.

    _field_key is set either by the namespace= kwarg on the schema class, or by
    the @settings decorator for LibrarySettings, or by register_schema() for
    GlobalSettings.
    """

    def __init__(
        self,
        default: Any,
        *,
        type_: 'type | None' = None,
        label: str = '',
        description: str = '',
        category: str = 'general',
        order: int = 0,
        min: Any = None,
        max: Any = None,
        choices: 'list | dict | Callable | None' = None,
        widget: 'str | None' = None,
        on_change: 'str | None' = None,
        stored: bool = True,
        validator: 'Callable | None' = None,
    ) -> None:
        self._default = default
        self._type = type_ if type_ is not None else type(default)
        self._label = label
        self._description = description
        self._category = category
        self._order = order
        self._min = min
        self._max = max
        self._choices = choices
        self._widget = widget
        self._on_change = on_change
        self._stored = stored
        self._validator = validator
        self._attr_name: str = ''   # set by __set_name__
        self._field_key: str = ''   # set by schema __init_subclass__ or @settings

    def validate(self, value: Any) -> bool:
        """Return True if *value* is valid for this setting."""
        if self._validator is not None:
            return self._validator(value)
        return True

    def __get__(self, obj: Any, objtype: type | None = None) -> Any:
        if obj is None:
            return self   # class-level access -> descriptor itself (used as mirrors= target)
        raise AttributeError(
            f"SettingDescriptor '{self._attr_name}' cannot be accessed on an instance. "
            f"Use GlobalSettingsRegistry.resolve() to get values."
        )

    def __set__(self, obj: Any, value: Any) -> None:
        raise AttributeError(
            f"SettingDescriptor '{self._attr_name}' is read-only on instances. "
            f"Use GlobalSettingsRegistry.set_global() to change global values."
        )


def setting(
    default: Any,
    *,
    type_: 'type | None' = None,
    label: str = '',
    description: str = '',
    category: str = 'general',
    order: int = 0,
    min: Any = None,
    max: Any = None,
    choices: 'list | dict | Callable | None' = None,
    widget: 'str | None' = None,
    on_change: 'str | None' = None,
    stored: bool = True,
    validator: 'Callable | None' = None,
) -> Any:
    """
    Declare a field on a GlobalSettings or LibrarySettings schema class.

    For node-local settings use prop() on a Bag subclass instead.
    """
    return SettingDescriptor(
        default,
        type_=type_,
        label=label,
        description=description,
        category=category,
        order=order,
        min=min,
        max=max,
        choices=choices,
        widget=widget,
        on_change=on_change,
        stored=stored,
        validator=validator,
    )
