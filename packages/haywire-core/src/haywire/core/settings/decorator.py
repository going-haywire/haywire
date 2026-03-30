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
    Decorator for library-global settings classes.

    Sets class_identity (required by BaseRegistry), class_library (for hot-reload),
    _namespace, and _field_key on all descriptor fields (namespace known at decoration time).

    Args:
        namespace:   Dot-separated settings namespace (e.g. 'my_lib.ui').
                     Also used as registry_id for BaseRegistry compatibility.
        label:       Human-readable display name. Defaults to namespace.
        description: Human-readable description. Defaults to ''.

    Usage:
        @settings(namespace='my_lib')
        class MyLibSettings(LibrarySettings):
            bg_color: Color = field('#1e1e2e', label='Node Background')

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

        library_identity = derive_library_identity(inner_cls)
        library_id = library_identity.id if library_identity else None

        inner_cls.class_identity = SettingsClassIdentity(
            registry_id=namespace,
            namespace=namespace,
            registry_key=reg_key(library_id, "settings", namespace),
            label=label or namespace,
            description=description,
        )
        inner_cls._namespace = namespace
        inner_cls.class_library = library_identity
        inner_cls._auto_register = True  # readable flag; registry uses class_identity for detection

        # Set _field_key on all prop descriptors (namespace known at decoration time)
        for name, descriptor in inner_cls._prop_fields().items():
            descriptor._field_key = f"{namespace}.{name}"

        return inner_cls

    return decorator
