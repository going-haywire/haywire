# haywire/core/settings/decorators.py
"""
Decorators for the Haywire settings system.

@library_settings(namespace=...) — marks a LibrarySettings subclass for auto-discovery
    by GlobalSettingsRegistry when a library calls add_folder().

Consistent with @node, @editor, @panel, @theme pattern:
  - Derives library identity via derive_library_identity()
  - Attaches class_library so hot-reload works
  - Validates the base class with issubclass()
"""

from __future__ import annotations
from dataclasses import dataclass, field

from haywire.core.library.utils import derive_library_identity, reg_key


@dataclass
class SettingsClassIdentity:
    """
    Identity object attached to LibrarySettings / GlobalSettings classes.

    Required by BaseRegistry._register() — analogous to how @node attaches
    NodeClassIdentity, @editor attaches EditorClassIdentity, etc.
    """
    namespace:    str
    registry_key: str
    label:        str = ''


def library_settings(namespace: str, label: str = ''):
    """
    Decorator for library-global settings classes.

    Sets class_identity (required by BaseRegistry), class_library (for hot-reload),
    _namespace, and _field_key on all descriptor fields (namespace known at decoration time).

    Args:
        namespace: Dot-separated settings namespace (e.g. 'my_lib.ui').
        label:     Human-readable display name. Defaults to namespace.

    Usage:
        @library_settings(namespace='my_lib')
        class MyLibSettings(LibrarySettings):
            bg_color: Color = setting('#1e1e2e', label='Node Background')

    Auto-discovered by GlobalSettingsRegistry when the library calls:
        settings_registry.add_folder(path, library_identity)
    """
    def decorator(cls):
        # Lazy import to avoid circular dependency (schema imports descriptors)
        from haywire.core.settings.schema import LibrarySettings, GlobalSettings
        if not issubclass(cls, (LibrarySettings, GlobalSettings)):
            raise TypeError(
                f"@library_settings can only be applied to LibrarySettings or GlobalSettings "
                f"subclasses, got {cls}"
            )

        library_identity = derive_library_identity(cls)
        library_id = library_identity.id if library_identity else None

        cls.class_identity = SettingsClassIdentity(
            namespace    = namespace,
            registry_key = reg_key(library_id, 'settings', namespace),
            label        = label or namespace,
        )
        cls._namespace = namespace
        cls.class_library = library_identity
        cls._auto_register = True  # readable flag; registry uses class_identity for detection

        # Set _field_key on all descriptors (namespace known at decoration time)
        for name, descriptor in cls._fields.items():
            descriptor._field_key = f'{namespace}.{name}'

        return cls

    return decorator
