# haywire/core/settings/schema.py
"""
Base schema classes for the Haywire global settings registry.

These are used exclusively by the GlobalSettingsRegistry for framework built-in
settings (GlobalSettings) and library-wide TOML settings (LibrarySettings).

Node-local settings use Settings subclasses with setting() — see haywire.core.settings.
"""

from __future__ import annotations
from typing import ClassVar

from haywire.core.settings.settings import Settings


class GlobalSettings(Settings):
    """
    Framework built-in settings (e.g. NodeUISettings, DebugSettings).

    Subclass with a namespace= kwarg to register field keys automatically:
        class NodeUISettings(GlobalSettings, namespace='ui.node'):
            bg_color: Color = setting('#ffffff', label='Background Color')

    Deep inheritance (subclassing a GlobalSettings subclass) is blocked to
    prevent namespace collisions from inherited fields.

    These classes are class-only (never instantiated) — the registry reads
    _prop_fields() for metadata.
    """

    _namespace: ClassVar[str] = ""

    def __init_subclass__(cls, namespace: str = "", **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        # Block deep inheritance: only direct subclasses of GlobalSettings allowed
        for base in cls.__bases__:
            if base is not GlobalSettings and isinstance(base, type) and issubclass(base, GlobalSettings):
                raise TypeError(
                    f"Subclassing a GlobalSettings subclass is not allowed. "
                    f"'{cls.__name__}' cannot extend '{base.__name__}'. "
                    f"Extend GlobalSettings directly instead."
                )

        if namespace:
            cls._namespace = namespace
            for name, val in cls.__dict__.items():
                from haywire.core.settings.descriptor import setting  # noqa: PLC0415

                if isinstance(val, setting):
                    val._field_key = f"{namespace}.{name}"


class LibrarySettings(Settings):
    """
    Library-global settings. Must be decorated with @settings to be registered
    with GlobalSettingsRegistry.

    Used to define library-wide TOML-configurable defaults.  Node authors use
    Settings subclasses with setting() for per-node settings.

    Deep inheritance (subclassing a LibrarySettings subclass) is blocked to
    prevent namespace collisions from inherited fields.
    """

    _namespace: ClassVar[str] = ""

    def __init_subclass__(cls, namespace: str = "", **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        # Block deep inheritance: only direct subclasses of LibrarySettings allowed
        for base in cls.__bases__:
            if base is not LibrarySettings and isinstance(base, type) and issubclass(base, LibrarySettings):
                raise TypeError(
                    f"Subclassing a LibrarySettings subclass is not allowed. "
                    f"'{cls.__name__}' cannot extend '{base.__name__}'. "
                    f"Extend LibrarySettings directly instead."
                )

        if namespace:
            cls._namespace = namespace
            for name, val in cls.__dict__.items():
                from haywire.core.settings.descriptor import setting  # noqa: PLC0415

                if isinstance(val, setting):
                    val._field_key = f"{namespace}.{name}"
