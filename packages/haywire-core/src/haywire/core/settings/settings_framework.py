# haywire/core/settings/settings_framework.py
"""
FrameworkSettings — framework/app-defined settings schemas.

Defined in haywire-core or haywire-studio; auto-register via _pending_global
at SettingsRegistry init time. May be instantiated by framework classes
for live reactive access — no explicit registry injection needed.

For haywire-core and haywire-studio extension only. Node and library authors
should use NodeSettings or LibrarySettings instead.

Gets cls._registry written by SettingsRegistry at registration time, so
instantiation with no args produces a fully registry-wired instance.
"""

from __future__ import annotations
from typing import ClassVar

from typing_extensions import dataclass_transform

from haywire.core.library.identity import LibraryIdentity
from haywire.core.settings.decorator import SettingsClassIdentity
from haywire.core.settings.descriptor import persistent_setting, setting
from haywire.core.settings.settings import Settings


# Module-level queue: FrameworkSettings subclasses defined before the registry exists
# are appended here and drained by SettingsRegistry.__init__.
_pending_global: list[type[FrameworkSettings]] = []


@dataclass_transform(field_specifiers=(setting,))
class FrameworkSettings(Settings):
    """
    Framework/app-defined settings schema.

    For use by haywire-core and haywire-studio internals only.
    Node authors should use NodeSettings; library authors should use LibrarySettings.

    Subclass with a ``namespace=`` kwarg; registration is automatic, and
    subclassing a subclass raises ``TypeError``. A ``mirrors=`` field (including
    ``shadow()``/``watch()``) is not allowed and raises ``TypeError`` too.

    Consumers instantiate directly for live reactive access, with no explicit
    registry injection::

        class ExecutionSettings(FrameworkSettings, namespace='execution'):
            max_threads = setting[INT](4, label='Max Threads')

        self.settings = ExecutionSettings()   # fully wired
        self.settings.max_threads = 8         # writes to the registry, notifies
        self.settings._subscribe(self.on_max_threads_change)
    """

    # Injected by the @settings decorator (or by __init_subclass__ via the
    # class-signature namespace= form); declared here so hot-reload and type
    # checkers see them as class attributes.
    class_identity: ClassVar[SettingsClassIdentity]
    class_library: ClassVar[LibraryIdentity]

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

            for name, val in cls._settings_descriptors().items():
                if val._mirror_key:
                    raise TypeError(
                        f"mirrors= is not allowed in FrameworkSettings: '{cls.__name__}.{name}'. "
                        f"Use plain setting() without mirrors=, shadow(), or watch()."
                    )
                val._setting_key = f"{namespace}.{name}"
                # _mirror_key stays empty: it means "mirrors another setting".
                # Persistence keys off _setting_key and the registry-owned cell.
                val.__class__ = persistent_setting

            # Self-registration: queue or register immediately
            if FrameworkSettings._registry is not None:
                FrameworkSettings._registry.register_schema(cls)
                cls._registry = FrameworkSettings._registry
            else:
                _pending_global.append(cls)

    def __init__(self) -> None:
        super().__init__(registry=type(self)._registry)
