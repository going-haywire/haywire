# haywire/ui/themes/theme_decorators.py
"""
Decorators for registering WorkbenchTheme and NodeTheme classes.

@theme(id=...) — marks a WorkbenchTheme or NodeTheme subclass for auto-discovery
by ThemeRegistry when a library calls add_folder().

Consistent with @node, @editor, @panel, @library_settings pattern:
  - Derives library identity via derive_library_identity()
  - Attaches class_library so hot-reload works
  - Auto-detects theme_type from the base class
  - Validates the base class with issubclass()
"""

from __future__ import annotations
from dataclasses import dataclass

from haywire.core.library.utils import derive_library_identity, reg_key


@dataclass
class ThemeClassIdentity:
    """Identity metadata stored on decorated theme classes."""
    theme_id:     str
    theme_type:   str         # 'workbench' or 'node'
    registry_key: str
    label:        str = ''


def theme(cls=None, /, *, id: str, label: str = ''):
    """
    Decorator that registers a WorkbenchTheme or NodeTheme subclass.

    The theme type ('workbench' or 'node') is auto-detected from the base class —
    no need to specify it explicitly.

    Args:
        id:    Unique theme identifier (e.g. 'haywire-dark', 'default').
        label: Human-readable display name. Defaults to id.

    Usage:
        @theme(id='haywire-dark', label='Haywire Dark')
        class HaywireDarkTheme(WorkbenchTheme):
            bg_page = '#12121e'
            ...

        @theme(id='default', label='Default Node Theme')
        class DefaultNodeTheme(NodeTheme):
            header_bg = '#252540'
            ...
    """
    def decorator(inner_cls):
        # Lazy imports to avoid circular dependencies
        from haywire.ui.themes.workbench import WorkbenchTheme
        from haywire.ui.themes.node_theme import NodeTheme

        if issubclass(inner_cls, WorkbenchTheme):
            theme_type = 'workbench'
        elif issubclass(inner_cls, NodeTheme):
            theme_type = 'node'
        else:
            raise TypeError(
                f"@theme can only be applied to WorkbenchTheme or NodeTheme subclasses, "
                f"got {inner_cls}"
            )

        library_identity = derive_library_identity(inner_cls)
        library_id = library_identity.id if library_identity else None
        registry_key = reg_key(library_id, f'theme:{theme_type}', id)

        inner_cls.class_identity = ThemeClassIdentity(
            theme_id=id,
            theme_type=theme_type,
            registry_key=registry_key,
            label=label or id,
        )
        inner_cls.class_library = library_identity
        inner_cls._theme_id = id
        inner_cls._auto_register = True
        return inner_cls

    return decorator if cls is None else decorator(cls)
