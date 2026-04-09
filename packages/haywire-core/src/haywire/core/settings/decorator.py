# haywire/core/settings/decorators.py
"""
Decorators for the Haywire settings system.

@settings(namespace=...) — marks a LibrarySettings subclass for auto-discovery
    by FrameworkSettingsRegistry when a library calls add_folder().

Consistent with @node, @editor, @panel, @theme pattern:
  - Derives library identity via derive_library_identity()
  - Attaches class_library so hot-reload works
  - Validates the base class with issubclass()
"""

from __future__ import annotations
from dataclasses import dataclass

from haywire.core.library.utils import derive_library_identity, reg_key
from haywire.core.registry.identity import BaseIdentity


@dataclass
class SettingsClassIdentity(BaseIdentity):
    """
    Identity object attached to LibrarySettings / FrameworkSettings classes.

    Required by BaseRegistry._register() — analogous to how @node attaches
    NodeIdentity, @editor attaches EditorClassIdentity, etc.

    registry_id mirrors namespace (the dot-separated TOML key prefix) so that
    BaseRegistry lookups work consistently across all registry types.
    """

    namespace: str = ""


def settings(namespace: str, label: str = "", description: str = ""):
    """
    Decorator for library settings classes.

    Sets class_identity (required by BaseRegistry), class_library (for hot-reload),
    _namespace, and _field_key on all descriptor fields (namespace known at decoration time).

    Args:
        namespace:   Dot-separated sub-namespace (e.g. 'ui.info').
                     the actual namespace is derived from the library
                     identity and this sub namespace (e.g. 'my_lib.ui.info').
        label:       Human-readable display name. Defaults to namespace.
        description: Human-readable description. Defaults to ''.

    Usage:
        @settings(namespace='ui.info')
        class MyLibSettings(LibrarySettings):
            bg_color: Color = field('#1e1e2e', label='Node Background')

    Notes:
        the namespace of the field bg_color would be 'my_lib.ui.info.bg_color'

    Auto-discovered by FrameworkSettingsRegistry when the library calls:
        settings_registry.add_folder(path, library_identity)
    """

    def decorator(inner_cls):
        # Lazy import to avoid circular dependency (schema imports descriptors)
        from haywire.core.settings.schema import LibrarySettings, FrameworkSettings  # noqa: PLC0415

        if not issubclass(inner_cls, (LibrarySettings, FrameworkSettings)):
            raise TypeError(
                f"@settings can only be applied to LibrarySettings or FrameworkSettings "
                f"subclasses, got {inner_cls}"
            )

        _registry_id = inner_cls.__name__

        library_identity = derive_library_identity(inner_cls)
        library_id = library_identity.id if library_identity else None

        registry_key = reg_key(library_id, "settings", _registry_id)

        full_namespace = library_id + "." + namespace if library_id else namespace

        inner_cls.class_identity = SettingsClassIdentity(
            namespace=full_namespace,
            registry_id=_registry_id,
            registry_key=registry_key,
            label=label or namespace,
            description=description,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
        )
        inner_cls._namespace = namespace
        inner_cls.class_library = library_identity

        # Set _field_key on all prop descriptors (namespace known at decoration time)
        for name, descriptor in inner_cls._property_fields().items():
            descriptor._field_key = f"{namespace}.{name}"

        return inner_cls

    return decorator
