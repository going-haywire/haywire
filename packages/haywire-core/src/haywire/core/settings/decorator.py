# haywire/core/settings/decorators.py
"""
Decorators for the Haywire settings system.

@settings(namespace=...) — marks a LibrarySettings subclass for auto-discovery
    by SettingsRegistry when a library folder is scanned (``add_folder()``).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, TypeVar

from haywire.core.library.utils import SETTING, derive_library_identity, reg_key
from haywire.core.registry.identity import BaseIdentity

# Preserves the decorated class's type, so the decorator's return type is the
# class itself rather than `Any` and IDE completions survive decoration.
_TSettings = TypeVar("_TSettings", bound=type)


@dataclass
class SettingsClassIdentity(BaseIdentity):
    """
    Identity object attached to LibrarySettings / FrameworkSettings classes.

    ``namespace`` is the class's settings namespace — library-qualified
    (``my_lib.ui.info``) when ``@settings`` built the identity.
    """

    namespace: str = ""


def settings(
    namespace: str, label: str = "", description: str = "", deprecation_warning: str = ""
) -> Callable[[_TSettings], _TSettings]:
    """
    Decorator for library settings classes.

    Sets ``class_identity``, ``class_library``, ``_namespace``, and
    ``_setting_key`` on every descriptor field, and promotes each field to
    ``persistent_setting`` so writes route through the registry's workspace
    tier. Raises ``TypeError`` unless the class subclasses ``LibrarySettings``
    or ``FrameworkSettings``.

    Args:
        namespace:   Dot-separated sub-namespace (e.g. 'ui.info'). Each field's
                     ``_setting_key`` becomes ``<namespace>.<field>``, while the
                     class identity's namespace is prefixed with the library
                     name (e.g. 'my_lib.ui.info').
        label:       Human-readable display name. Defaults to namespace.
        description: Human-readable description. Defaults to ''.
        deprecation_warning: Optional human-readable message shown when this
            settings class is listed anywhere. Empty string means not deprecated.

    Example::

        @settings(namespace='ui.info')
        class MyLibSettings(LibrarySettings):
            bg_color = setting[COLOR]('#1e1e2e', label='Node Background')
    """

    def decorator(inner_cls: _TSettings) -> _TSettings:
        # Lazy import to avoid circular dependency (settings_library/settings_framework import descriptors)
        from haywire.core.settings.settings_library import LibrarySettings  # noqa: PLC0415
        from haywire.core.settings.settings_framework import FrameworkSettings  # noqa: PLC0415
        from haywire.core.settings.descriptor import persistent_setting  # noqa: PLC0415

        if not issubclass(inner_cls, (LibrarySettings, FrameworkSettings)):
            raise TypeError(
                f"@settings can only be applied to LibrarySettings or FrameworkSettings "
                f"subclasses, got {inner_cls}"
            )

        _registry_id = inner_cls.__name__

        library_identity = derive_library_identity(inner_cls)
        library_id = library_identity.name

        registry_key = reg_key(library_id, SETTING, _registry_id)

        full_namespace = library_id + "." + namespace

        inner_cls.class_identity = SettingsClassIdentity(
            namespace=full_namespace,
            registry_id=_registry_id,
            registry_key=registry_key,
            label=label or namespace,
            description=description,
            deprecation_warning=deprecation_warning,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
        )
        inner_cls._namespace = namespace
        inner_cls.class_library = library_identity

        # Same stamping as the class-signature `namespace=` path in
        # FrameworkSettings/LibrarySettings.__init_subclass__.
        for attr_name, descriptor in inner_cls._settings_descriptors().items():
            descriptor._setting_key = f"{namespace}.{attr_name}"
            descriptor.__class__ = persistent_setting

        return inner_cls

    return decorator
