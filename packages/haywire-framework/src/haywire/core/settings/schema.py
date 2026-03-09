# haywire/core/settings/schema.py
"""
Base schema classes for the Haywire settings system.

Hierarchy:
    _SettingsSchema          — shared base: collects _SettingDescriptor fields
        NodeSettings         — for node-local Settings inner classes
        LibrarySettings      — for library-global settings (requires @library_settings)
        GlobalSettings       — for framework built-in settings (namespace= kwarg required)
        WorkbenchTheme       — defined separately in ui/themes/workbench.py
        NodeTheme            — defined separately in ui/themes/node_theme.py
"""

from __future__ import annotations
from typing import ClassVar, TYPE_CHECKING

from .descriptors import SettingDescriptor

if TYPE_CHECKING:
    pass


class _SettingsSchema:
    """
    Shared base for all settings schema classes.

    __init_subclass__ automatically collects SettingDescriptor instances from
    the class body into cls._fields. A fresh dict is created per class — never
    inherited from parent — so subclasses don't bleed fields into each other.

    When a namespace= kwarg is provided at the class line:
        class MySettings(GlobalSettings, namespace='ui.node'):
    _namespace is set and _full_key is set on all collected descriptors immediately.
    """

    _fields: ClassVar[dict[str, SettingDescriptor]]
    _namespace: ClassVar[str] = ''

    def __init_subclass__(cls, namespace: str = '', **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        # Fresh dict per class — NEVER inherit from parent
        cls._fields = {}

        # Collect only this class's own descriptors (not inherited ones)
        for name, val in cls.__dict__.items():
            if isinstance(val, SettingDescriptor):
                # __set_name__ was already called by Python — _attr_name is set
                cls._fields[name] = val

        # Set namespace and _full_key when namespace kwarg is provided.
        # class_identity is NOT set here — that is the decorator's job.
        if namespace:
            cls._namespace = namespace
            for name, descriptor in cls._fields.items():
                descriptor._full_key = f'{namespace}.{name}'


class NodeSettings(_SettingsSchema):
    """
    Marker base for node-local settings schemas (inner class on BaseNode subclasses).

    _namespace and _full_key are set by the @node decorator after the outer
    class is known. Explicit override is possible:
        class node(NodeSettings, namespace='my.custom.ns'):
            ...

    NodeSettings are never registered with GlobalSettingsRegistry — they are purely
    per-node, stored in the graph file.
    """


class LibrarySettings(_SettingsSchema):
    """
    Library-global settings. Must be decorated with @library_settings to be
    registered with GlobalSettingsRegistry (the decorator sets class_identity).

    The namespace= kwarg on the class line is optional — @library_settings sets
    it authoritatively (and overrides any kwarg-set namespace).

    Discovered automatically via GlobalSettingsRegistry folder scan when
    library_registry.add_class_registry(GlobalSettingsRegistry, settings_registry)
    is active and the library calls settings_registry.add_folder(path, identity).
    """


class GlobalSettings(_SettingsSchema):
    """
    Framework built-in settings (replaces builtins/ui_node.py etc.).

    namespace= kwarg required at the class line. No decorator needed —
    register_schema() creates class_identity from _namespace at registration time.

    Registered explicitly via register_schema() in builtins/__init__.py,
    not via folder scan.

    Example:
        class NodeUISettings(GlobalSettings, namespace='ui.node'):
            bg_color: Color = setting('#ffffff', label='Background Color')
    """


class _EmptyNodeSettings(NodeSettings):
    """
    Fallback schema used by SettingsHolder when a node class has no inner
    Settings class. Has no fields — zero overhead.
    """
