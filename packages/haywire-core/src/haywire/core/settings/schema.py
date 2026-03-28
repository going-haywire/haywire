# haywire/core/settings/schema.py
"""
Base schema classes for the Haywire settings registry.

FrameworkSettings — framework/app-defined settings schemas.
    Defined in haywire-core or haywire-studio; auto-register via _pending_global
    at SettingsRegistry init time. May be instantiated by framework classes
    for live reactive access — no explicit registry injection needed.

    For haywire-core and haywire-studio extension only. Node and library authors
    should use NodeSettings or LibrarySettings instead.

LibrarySettings — library plugin-defined settings schemas.
    Registered via BaseRegistry hot-reload machinery (_register_class / _unregister_class).
    May be instantiated by library code for live reactive access.

Both classes get cls._registry written by SettingsRegistry at registration time,
so instantiation with no args produces a fully registry-wired instance.
"""

from __future__ import annotations
from typing import ClassVar, TYPE_CHECKING

from haywire.core.settings.settings import Settings

if TYPE_CHECKING:
    from haywire.core.settings.registry import SettingsRegistry


# Module-level queue: FrameworkSettings subclasses defined before the registry exists
# are appended here and drained by SettingsRegistry.__init__.
_pending_global: list[type[FrameworkSettings]] = []


class FrameworkSettings(Settings):
    """
    Framework/app-defined settings schema.

    For use by haywire-core and haywire-studio internals only.
    Node authors should use NodeSettings; library authors should use LibrarySettings.

    Subclass with a namespace= kwarg:
        class ExecutionSettings(FrameworkSettings, namespace='execution'):
            max_threads: int = setting(4, label='Max Threads')

    Registration is automatic:
    - If SettingsRegistry does not yet exist: queued in _pending_global,
      drained when the registry is created.
    - If the registry already exists (late import): registered immediately.

    After registration, cls._registry holds the registry back-reference, so:
        self.settings = ExecutionSettings()   # fully wired, no explicit injection
    """

    _namespace: ClassVar[str] = ""
    _registry: ClassVar["SettingsRegistry | None"] = None

    def __init_subclass__(cls, namespace: str = "", **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        # Block deep inheritance
        for base in cls.__bases__:
            if (
                base is not FrameworkSettings
                and isinstance(base, type)
                and issubclass(base, FrameworkSettings)
            ):
                raise TypeError(
                    f"Subclassing a FrameworkSettings subclass is not allowed. "
                    f"'{cls.__name__}' cannot extend '{base.__name__}'. "
                    f"Extend FrameworkSettings directly instead."
                )

        if namespace:
            cls._namespace = namespace
            from haywire.core.settings.descriptor import setting  # noqa: PLC0415

            for name, val in cls.__dict__.items():
                if isinstance(val, setting):
                    val._field_key = f"{namespace}.{name}"

            # Self-registration: queue or register immediately
            if FrameworkSettings._registry is not None:
                # Registry already exists (late import / safety guard) — register now
                FrameworkSettings._registry.register_schema(cls)
                cls._registry = FrameworkSettings._registry
            else:
                _pending_global.append(cls)

    def __init__(self) -> None:
        super().__init__(registry=type(self)._registry)


class LibrarySettings(Settings):
    """
    Library plugin-defined settings schema.

    Must be decorated with @settings to be discoverable by BaseRegistry:

        @settings(namespace='my_lib.general', label='My Library')
        class GeneralSettings(LibrarySettings):
            quality: int = setting(80, label='Quality')

    @settings sets class_identity (required by BaseRegistry._class_filter),
    class_library (for hot-reload), _namespace, and _field_key on all descriptors.

    Registration is via BaseRegistry hot-reload machinery — SettingsRegistry
    inherits BaseRegistry and calls _register_class / _unregister_class as libraries
    are loaded and hot-reloaded.

    After registration, cls._registry holds the registry back-reference, so:
        self.settings = GeneralSettings()   # fully wired, no explicit injection
    """

    _namespace: ClassVar[str] = ""
    _registry: ClassVar["SettingsRegistry | None"] = None

    def __init_subclass__(cls, namespace: str = "", **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        # Block deep inheritance
        for base in cls.__bases__:
            if base is not LibrarySettings and isinstance(base, type) and issubclass(base, LibrarySettings):
                raise TypeError(
                    f"Subclassing a LibrarySettings subclass is not allowed. "
                    f"'{cls.__name__}' cannot extend '{base.__name__}'. "
                    f"Extend LibrarySettings directly instead."
                )

        if namespace:
            cls._namespace = namespace
            from haywire.core.settings.descriptor import setting  # noqa: PLC0415

            for name, val in cls.__dict__.items():
                if isinstance(val, setting):
                    val._field_key = f"{namespace}.{name}"

        # No registry touch here — registration handled by BaseRegistry hot-reload path

    def __init__(self) -> None:
        super().__init__(registry=type(self)._registry)
