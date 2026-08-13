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

from typing import Any

from haywire.core.library.utils import THEME, derive_library_identity, reg_key
from haywire.ui.themes.identity import ThemeClassIdentity


def theme(**kwargs: Any):
    """
    Decorator that registers a WorkbenchTheme or NodeTheme subclass.

    Always invoked with parentheses — `@theme(...)` or `@theme()`. The bare
    `@theme` form (no parens) is not supported.

    The theme type ('workbench' or 'node') is auto-detected from the base class —
    no need to specify it explicitly.

    Accepted keys (splatted into ``ThemeClassIdentity``; an unknown key raises
    ``TypeError`` at class-definition time):
        label:        Human-readable display name. Defaults to registry_id.
        description:  Human-readable description. Defaults to ''.
        registry_id:  Unique theme identifier (e.g. 'haywire-dark', 'default').
                      Defaults to the class name. Used as the final segment of the
                      registry_key, which is the canonical lookup key.
        deprecation_warning: Optional human-readable message shown when this
            theme is listed anywhere. Empty string means not deprecated.
        hidden: When True, the theme is registered and usable but excluded from
            author-facing selection UIs (the theme picker). Used by testing
            themes. See the glossary term **Hidden component**.

    ``registry_key``, ``theme_type``, ``class_name`` and ``module`` are derived
    by the decorator and must not be passed.

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

        identity_kwargs = dict(kwargs)
        _registry_id = identity_kwargs.pop("registry_id", None) or inner_cls.__name__
        _label = identity_kwargs.pop("label", "") or _registry_id

        library_identity = derive_library_identity(inner_cls)
        _registry_key = reg_key(library_identity.name, f"{THEME}:{theme_type}", _registry_id)

        # Remaining keys (description, deprecation_warning, hidden, …) splat straight
        # into the identity; an unknown key surfaces as a TypeError there.
        inner_cls.class_identity = ThemeClassIdentity(
            registry_id=_registry_id,
            theme_type=theme_type,
            registry_key=_registry_key,
            label=_label,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
            **identity_kwargs,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator
