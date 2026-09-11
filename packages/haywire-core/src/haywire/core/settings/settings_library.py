# haywire/core/settings/settings_library.py
"""
LibrarySettings — library plugin-defined settings schemas.

Registered via BaseRegistry hot-reload machinery (_register_class /
_unregister_class). May be instantiated by library code for live reactive
access.

Gets cls._registry written by SettingsRegistry at registration time, so
instantiation with no args produces a fully registry-wired instance.
"""

from __future__ import annotations
from typing import ClassVar

from typing_extensions import dataclass_transform

from haywire.core.library.identity import LibraryIdentity
from haywire.core.settings.decorator import SettingsClassIdentity
from haywire.core.settings.descriptor import persistent_setting, setting, shadow
from haywire.core.settings.settings import Settings


@dataclass_transform(field_specifiers=(setting, shadow))
class LibrarySettings(Settings):
    """
    Library plugin-defined settings schema.

    Decorate with ``@settings`` to be discoverable by ``SettingsRegistry``.
    Subclassing a subclass raises ``TypeError``, and so does a ``mirrors=``
    field (including ``shadow()``/``watch()``).

    After registration ``cls._registry`` holds the registry back-reference, so
    a bare construction is fully wired::

        @settings(namespace='general', label='My Library')
        class GeneralSettings(LibrarySettings):
            quality = setting[INT](80, label='Quality')

        self.settings = GeneralSettings()   # no explicit injection
    """

    # Injected by the @settings decorator; declared here so hot-reload and type
    # checkers see them as class attributes.
    class_identity: ClassVar[SettingsClassIdentity]
    class_library: ClassVar[LibraryIdentity]

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

            for name, val in cls._settings_descriptors().items():
                if val._mirror_key:
                    raise TypeError(
                        f"mirrors= is not allowed in LibrarySettings: '{cls.__name__}.{name}'. "
                        f"Use plain setting() without mirrors=, shadow(), or watch()."
                    )
                val._setting_key = f"{namespace}.{name}"
                # _mirror_key stays empty: it means "mirrors another setting".
                # Persistence keys off _setting_key and the registry-owned cell.
                val.__class__ = persistent_setting

        # No registry touch here — registration runs on the BaseRegistry hot-reload path.

    def __init__(self) -> None:
        super().__init__(registry=type(self)._registry)
