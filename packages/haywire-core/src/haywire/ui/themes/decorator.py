# haywire/ui/themes/theme_decorators.py
"""
Decorators for registering WorkbenchTheme and NodeTheme classes.

@theme(...) — marks a WorkbenchTheme or NodeTheme subclass for auto-discovery
by ThemeRegistry when a library calls add_folder().

Consistent with @node, @editor, @panel, @settings pattern:
  - Derives library identity via derive_library_identity()
  - Attaches class_library so hot-reload works
  - Auto-detects theme_type from the base class
  - Validates the base class with issubclass()
"""

from __future__ import annotations
from dataclasses import dataclass

from haywire.core.library.utils import derive_library_identity, reg_key
from haywire.core.registry.identity import BaseIdentity


@dataclass
class ThemeClassIdentity(BaseIdentity):
    """Identity metadata stored on decorated theme classes."""

    theme_type: str = ""  # 'workbench' or 'node'


def theme(
    cls=None,
    /,
    *,
    label: str = "",
    description: str = "",
    registry_id: str | None = None,
):
    """
    Decorator that registers a WorkbenchTheme or NodeTheme subclass.

    The theme type ('workbench' or 'node') is auto-detected from the base class —
    no need to specify it explicitly.

    Args:
        label:        Human-readable display name. Defaults to registry_id.
        description:  Human-readable description. Defaults to ''.
        registry_id:  Unique theme identifier (e.g. 'haywire-dark', 'default').
                      Defaults to the class name. Used as the final segment of the
                      registry_key, which is the canonical lookup key.

    Usage:
        @theme(label='Haywire Dark')
        class HaywireDarkTheme(WorkbenchTheme):
            bg_page = '#12121e'
            ...

        @theme(label='Default Node Theme')
        class DefaultNodeTheme(NodeTheme):
            header_bg = '#252540'
            ...
    """

    def decorator(inner_cls):
        # Lazy imports to avoid circular dependencies
        from haywire.ui.themes.workbench import WorkbenchTheme
        from haywire.ui.themes.node_theme import NodeTheme

        if issubclass(inner_cls, WorkbenchTheme):
            theme_type = "workbench"
        elif issubclass(inner_cls, NodeTheme):
            theme_type = "node"
        else:
            raise TypeError(
                f"@theme can only be applied to WorkbenchTheme or NodeTheme subclasses, got {inner_cls}"
            )

        _registry_id = registry_id or inner_cls.__name__
        _label = label or _registry_id

        library_identity = derive_library_identity(inner_cls)
        library_id = library_identity.id if library_identity else None
        _registry_key = reg_key(library_id, f"theme:{theme_type}", _registry_id)

        inner_cls.class_identity = ThemeClassIdentity(
            registry_id=_registry_id,
            theme_type=theme_type,
            registry_key=_registry_key,
            label=_label,
            description=description,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator if cls is None else decorator(cls)
