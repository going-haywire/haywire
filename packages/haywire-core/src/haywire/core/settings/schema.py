# haywire/core/settings/schema.py
"""
Base schema classes for the Haywire global settings registry.

GlobalSettings — framework/app-defined settings schemas.
    Defined in haywire-core or haywire-studio; auto-register via _pending_global
    at GlobalSettingsRegistry init time. May be instantiated by framework classes
    for live reactive access — no explicit registry injection needed.

LibrarySettings — library plugin-defined settings schemas.
    Registered via BaseRegistry hot-reload machinery (_register_class / _unregister_class).
    May be instantiated by library code for live reactive access.

Both classes get cls._registry written by GlobalSettingsRegistry at registration time,
so instantiation with no args produces a fully registry-wired instance.
"""

from __future__ import annotations
from typing import ClassVar, TYPE_CHECKING

from haywire.core.settings.settings import Settings

if TYPE_CHECKING:
    from haywire.core.settings.registry import GlobalSettingsRegistry


# Module-level queue: GlobalSettings subclasses defined before the registry exists
# are appended here and drained by GlobalSettingsRegistry.__init__.
_pending_global: list[type[GlobalSettings]] = []


class GlobalSettings(Settings):
    """
    Framework/app-defined settings schema.

    Subclass with a namespace= kwarg:
        class ExecutionSettings(GlobalSettings, namespace='execution'):
            max_threads: int = setting(4, label='Max Threads')

    Registration is automatic:
    - If GlobalSettingsRegistry does not yet exist: queued in _pending_global,
      drained when the registry is created.
    - If the registry already exists (late import): registered immediately.

    After registration, cls._registry holds the registry back-reference, so:
        self.settings = ExecutionSettings()   # fully wired, no explicit injection
    """

    _namespace: ClassVar[str] = ""
    _registry: ClassVar["GlobalSettingsRegistry | None"] = None

    def __init_subclass__(cls, namespace: str = "", **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)

        # Block deep inheritance
        for base in cls.__bases__:
            if base is not GlobalSettings and isinstance(base, type) and issubclass(base, GlobalSettings):
                raise TypeError(
                    f"Subclassing a GlobalSettings subclass is not allowed. "
                    f"'{cls.__name__}' cannot extend '{base.__name__}'. "
                    f"Extend GlobalSettings directly instead."
                )

        if namespace:
            cls._namespace = namespace
            from haywire.core.settings.descriptor import setting  # noqa: PLC0415

            for name, val in cls.__dict__.items():
                if isinstance(val, setting):
                    val._field_key = f"{namespace}.{name}"

            # Self-registration: queue or register immediately
            if GlobalSettings._registry is not None:
                # Registry already exists (late import / safety guard) — register now
                GlobalSettings._registry.register_schema(cls)
                cls._registry = GlobalSettings._registry
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

    Registration is via BaseRegistry hot-reload machinery — GlobalSettingsRegistry
    inherits BaseRegistry and calls _register_class / _unregister_class as libraries
    are loaded and hot-reloaded.

    After registration, cls._registry holds the registry back-reference, so:
        self.settings = GeneralSettings()   # fully wired, no explicit injection
    """

    _namespace: ClassVar[str] = ""
    _registry: ClassVar["GlobalSettingsRegistry | None"] = None

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
