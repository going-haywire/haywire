# haywire/core/settings/schema.py
"""
Base schema classes for the Haywire global settings registry.

These are used exclusively by the GlobalSettingsRegistry for framework built-in
settings (GlobalSettings) and library-wide TOML settings (LibrarySettings).

Node-local settings use Bag subclasses with prop() — see haywire.core.property.
"""

from __future__ import annotations
from typing import ClassVar

from .descriptors import SettingDescriptor


class _SettingsSchema:
    """
    Shared base for GlobalSettings and LibrarySettings schema classes.

    __init_subclass__ automatically collects SettingDescriptor instances from
    the class body into cls._fields. A fresh dict is created per class — never
    inherited from parent.

    When a namespace= kwarg is provided at the class line:
        class MySettings(GlobalSettings, namespace='ui.node'):
    _namespace is set and _field_key is set on all collected descriptors.
    """

    _fields: ClassVar[dict[str, SettingDescriptor]]
    _namespace: ClassVar[str] = ''

    def __init_subclass__(cls, namespace: str = '', **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        # Fresh dict per class — NEVER inherit from parent
        cls._fields = {}

        for name, val in cls.__dict__.items():
            if isinstance(val, SettingDescriptor):
                cls._fields[name] = val

        if namespace:
            cls._namespace = namespace
            for name, descriptor in cls._fields.items():
                descriptor._field_key = f'{namespace}.{name}'


class LibrarySettings(_SettingsSchema):
    """
    Library-global settings. Must be decorated with @settings to be registered
    with GlobalSettingsRegistry.

    Used to define library-wide TOML-configurable defaults.  Node authors use
    Bag subclasses with prop() for per-node settings.
    """


class GlobalSettings(_SettingsSchema):
    """
    Framework built-in settings (e.g. NodeUISettings, DebugSettings).

    namespace= kwarg required at the class line. Registered explicitly via
    register_schema() — not via folder scan.

    Example:
        class NodeUISettings(GlobalSettings, namespace='ui.node'):
            bg_color: Color = setting('#ffffff', label='Background Color')
    """
