# packages/haywire-core/src/haywire/ui/panel/decorator.py
"""
@panel decorator for marking classes as Haywire panel types.

Sets class_identity on the class. Does NOT register the class —
registration happens when the library calls add_folder() in
register_components(), following the same pattern as @renderer and @widget.

Usage::

    @panel(surface=SelectionMenu, label='Delete Selection')
    class DeleteSelectionPanel(BasePanel):
        actions: SelectionActions   # for type-checker visibility on self.actions

        def draw(self, ctx, layout):
            self.actions.delete_selection()

Inspector panels read state and need no host verbs, so they omit the
annotation entirely::

    @panel(surface=SettingsInspector, label='Workbench Settings')
    class ThemeSettingsPanel(BasePanel):
        def draw(self, ctx, layout):
            ...

The host injected into ``self.actions`` is decided by whatever *renders* the
panel — its surface's ``provides`` Protocol is checked against that host at
the point of nesting (see :meth:`BasePanel.render_surface`). The class-body
``actions:`` annotation is purely for the type-checker; the framework has
never read it.

A panel that renders further surfaces of its own declares them with
``hosts=``::

    @panel(surface=GraphContext, hosts=(GraphToolBar, GraphContextBody),
           label='Graph Context')
    class GraphContextPanel(BasePanel):
        def draw(self, ctx, layout):
            with layout:
                self.render_surface(GraphToolBar, ctx)
"""

from __future__ import annotations

from typing import Any, Union

from haywire.core.access import AccessTier
from haywire.core.library.utils import PANEL, derive_library_identity, reg_key
from haywire.core.session.handlers import validate_signal_types
from haywire.ui.surface import Surface

from .identity import PanelIdentity
from .base import BasePanel


def panel(**kwargs: Any):
    """Decorator to mark a class as a panel.

    Always invoked with parentheses — `@panel(...)`. ``surface=`` and
    ``label=`` are required.

    Accepted keys (the special keys below are validated/transformed here; the
    rest splat into ``PanelIdentity``, so an unknown key raises ``TypeError`` at
    class-definition time)::

        surface: Surface subclass this panel appears on. Required.
        hosts:   Tuple of Surface subclasses this panel may render itself,
                 via ``self.render_surface(S, ctx)``. Optional; the empty
                 default makes the panel a *leaf*.
        label:   Human-readable display label. Required.
        icon:    Optional Material Design icon name.
        order:   Sort priority (lower = higher in the panel list). Default 100.
        default_open: Whether the panel starts expanded. Defaults to True.
        description:  Human-readable description.
        registry_id:  Unique ID for this panel. Defaults to the class name.
        redraw_on:    Tuple of Signal subclasses the panel wants its host
                      editor to redraw on. Empty tuple means no subscriptions.
        access:       Minimum AccessTier needed to see this panel — an
            :class:`AccessTier` or its string value ('view', 'edit', 'admin').
            Defaults to 'view'. An unknown value raises ``ValueError`` at
            class-definition time.
        deprecation_warning: Optional human-readable message shown when this
            panel is listed anywhere. Empty string means not deprecated.
        hidden: When True, the panel is registered and usable but excluded from
            author-facing selection UIs. See the glossary term
            **Hidden component**.

    ``registry_key``, ``class_name`` and ``module`` are derived by the
    decorator and must not be passed.

    Raises:
        ValueError: If surface= or label= is missing.
        TypeError:  If surface= is not a Surface subclass, any hosts= entry
                    is not a Surface subclass, the decorated class is not a
                    BasePanel subclass, or any redraw_on= entry is not a
                    Signal subclass.
    """
    identity_kwargs = dict(kwargs)

    surface = identity_kwargs.pop("surface", None)
    if surface is None:
        raise ValueError("@panel requires surface= (Surface subclass).")
    if not (isinstance(surface, type) and issubclass(surface, Surface)):
        raise TypeError(f"@panel: surface= must be a Surface subclass, got {surface!r}")

    hosts = tuple(identity_kwargs.pop("hosts", ()) or ())
    for hosted in hosts:
        if not (isinstance(hosted, type) and issubclass(hosted, Surface)):
            raise TypeError(f"@panel: every hosts= entry must be a Surface subclass, got {hosted!r}")

    if identity_kwargs.get("label") is None:
        raise ValueError("@panel requires label=.")

    validated_redraw_on = validate_signal_types(
        "@panel(..., redraw_on=...)", tuple(identity_kwargs.pop("redraw_on", ())), allow_empty=True
    )

    # Coerce access to enum; raises ValueError at class-definition time on typo.
    access: Union[AccessTier, str] = identity_kwargs.pop("access", AccessTier.VIEW)
    identity_kwargs["access"] = AccessTier(access) if isinstance(access, str) else access

    def decorator(inner_cls):
        if not issubclass(inner_cls, BasePanel):
            raise TypeError(f"@panel can only be applied to BasePanel subclasses, got {inner_cls}")

        _registry_id = identity_kwargs.pop("registry_id", None) or inner_cls.__name__

        library_identity = derive_library_identity(inner_cls)
        _registry_key = reg_key(library_identity.name, PANEL, _registry_id)

        # Remaining keys (label, icon, order, default_open, description,
        # deprecation_warning, hidden, …) splat into the identity; an unknown key
        # surfaces as a TypeError there.
        inner_cls.class_identity = PanelIdentity(
            registry_id=_registry_id,
            registry_key=_registry_key,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
            surface=surface,
            hosts=hosts,
            redraw_on=validated_redraw_on,
            **identity_kwargs,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator
