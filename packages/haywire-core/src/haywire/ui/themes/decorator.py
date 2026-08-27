# haywire/ui/themes/theme_decorators.py
"""
Decorator for registering BaseTheme subclasses.

@theme(theme_type=..., ...) — marks a BaseTheme subclass for auto-discovery
by ThemeRegistry when a library calls add_folder(). ``theme_type`` is
required (``'workbench'`` or ``'node'``) — it decides where the studio
injects this theme's declarations (``:root`` vs ``.graph-canvas`` /
``.ui-node-slot``), the same role ``node_type`` plays for ``@node``.

Consistent with @node, @editor, @panel, @settings pattern:
  - Derives library identity via derive_library_identity()
  - Attaches class_library so hot-reload works
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from haywire.core.library.utils import THEME, derive_library_identity, reg_key
from haywire.ui.themes.identity import ThemeClassIdentity

T = TypeVar("T")

_VALID_THEME_TYPES = ("workbench", "node")


def theme(*, theme_type: str, **kwargs: Any) -> Callable[[type[T]], type[T]]:
    """
    Decorator that registers a BaseTheme subclass.

    Always invoked with parentheses — `@theme(...)`. The bare `@theme` form
    (no parens) is not supported.

    Args:
        theme_type: Required. ``'workbench'`` for the app shell (injected at
            ``:root``) or ``'node'`` for node/graph-scoped overrides
            (injected at ``.graph-canvas`` / ``.ui-node-slot``).
        label: Human-readable display name. Defaults to registry_id.
        description: Human-readable description. Defaults to ''.
        registry_id: Unique theme identifier (e.g. 'haywire-dark', 'default').
            Defaults to the class name. Used as the final segment of the
            registry_key, which is the canonical lookup key.
        deprecation_warning: Optional human-readable message shown when this
            theme is listed anywhere. Empty string means not deprecated.
        hidden: When True, the theme is registered and usable but excluded from
            author-facing selection UIs (the theme picker). Used by testing
            themes. See the glossary term **Hidden component**.

    ``registry_key``, ``class_name`` and ``module`` are derived by the
    decorator and must not be passed.

    Usage:
        @theme(theme_type='workbench', label='Haywire Dark')
        class HaywireDarkTheme(BaseTheme):
            bg_page = '#12121e'
            ...

        @theme(theme_type='node', label='Default Node Theme')
        class DefaultNodeTheme(BaseTheme):
            node_bg = '#1e1e2e'
            ...
    """
    if theme_type not in _VALID_THEME_TYPES:
        raise ValueError(f"@theme(theme_type=...) must be one of {_VALID_THEME_TYPES}, got {theme_type!r}")

    def decorator(inner_cls: type[T]) -> type[T]:
        from haywire.ui.themes.workbench import BaseTheme

        if not issubclass(inner_cls, BaseTheme):  # type: ignore[arg-type]
            raise TypeError(f"@theme can only be applied to BaseTheme subclasses, got {inner_cls}")

        identity_kwargs = dict(kwargs)
        _registry_id = identity_kwargs.pop("registry_id", None) or inner_cls.__name__
        _label = identity_kwargs.pop("label", "") or _registry_id

        library_identity = derive_library_identity(inner_cls)
        _registry_key = reg_key(library_identity.name, THEME, _registry_id)

        # Remaining keys (description, deprecation_warning, hidden, …) splat
        # straight into the identity; an unknown key surfaces as a TypeError.
        inner_cls.class_identity = ThemeClassIdentity(  # type: ignore[attr-defined]
            registry_id=_registry_id,
            theme_type=theme_type,
            registry_key=_registry_key,
            label=_label,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
            **identity_kwargs,
        )
        inner_cls.class_library = library_identity  # type: ignore[attr-defined]
        return inner_cls

    return decorator
