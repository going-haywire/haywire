# packages/haywire-core/src/haywire/ui/panel/decorator.py
"""
@panel decorator for marking classes as Haywire panel types.

Sets class_identity on the class. Does NOT register the class —
registration happens when the library calls add_folder() in
register_components(), following the same pattern as @renderer and @widget.

Usage::

    @panel(actions=SelectionContextActions, focus=SelectionFocus, label='Delete Selection')
    class DeleteSelectionPanel(BasePanel):
        actions: SelectionContextActions   # for type-checker visibility on self.actions

        def draw(self, ctx, layout):
            self.actions.delete_selection()

Display panels omit both the decorator arg and the annotation:

    @panel(focus=SettingsFocus, label='Workbench Settings')
    class ThemeSettingsPanel(BasePanel):
        def draw(self, ctx, layout):
            ...

The framework stores ``actions=`` on ``PanelIdentity.action_protocol`` and
uses it for routing (``PanelRegistry.get_panels_for_action``) and host
injection at mount time. The matching class-body annotation is recommended
for type-checker visibility but the framework does not read it.
"""

from __future__ import annotations

from typing import Any

from haywire.core.library.utils import PANEL, derive_library_identity, reg_key
from haywire.core.session.handlers import validate_signal_types

from .focus import Focus
from .identity import PanelIdentity
from .base import BasePanel


def panel(**kwargs: Any):
    """Decorator to mark a class as a panel.

    Always invoked with parentheses — `@panel(...)`. ``focus=`` and
    ``label=`` are required.

    Accepted keys (the special keys below are validated/transformed here; the
    rest splat into ``PanelIdentity``, so an unknown key raises ``TypeError`` at
    class-definition time):
        actions: Protocol/ABC class declaring the host contract this panel
                 mounts against. Optional — display panels omit it. When
                 set, the framework injects the host instance into
                 ``panel.actions`` at mount time (only if the host
                 structurally satisfies the protocol). Stored as
                 ``PanelIdentity.action_protocol``.
        focus:   Focus subclass that discriminates which session states
                 this panel applies to. Required.
        label:   Human-readable display label. Required.
        icon:    Optional Material Design icon name.
        order:   Sort priority (lower = higher in the panel list). Default 100.
        default_open: Whether the panel starts expanded. Defaults to True.
        description:  Human-readable description.
        registry_id:  Unique ID for this panel. Defaults to the class name.
        redraw_on:    Tuple of Signal subclasses the panel wants its host
                      editor to redraw on. Empty tuple means no subscriptions.
        deprecation_warning: Optional human-readable message shown when this
            panel is listed anywhere. Empty string means not deprecated.
        hidden: When True, the panel is registered and usable but excluded from
            author-facing selection UIs. See the glossary term
            **Hidden component**.

    ``registry_key``, ``class_name``, ``module``, ``editor_keys`` and
    ``scopes`` are derived by the decorator and must not be passed.

    Raises:
        ValueError: If focus= or label= is missing.
        TypeError:  If focus is not a Focus subclass, actions= (when set)
                    is not a class, the decorated class is not a BasePanel
                    subclass, or any redraw_on= entry is not a Signal subclass.
    """
    identity_kwargs = dict(kwargs)

    focus = identity_kwargs.pop("focus", None)
    if focus is None:
        raise ValueError("@panel requires focus= (Focus subclass).")
    if not (isinstance(focus, type) and issubclass(focus, Focus)):
        raise TypeError(f"@panel: focus= must be a Focus subclass, got {focus!r}")

    if identity_kwargs.get("label") is None:
        raise ValueError("@panel requires label=.")

    actions = identity_kwargs.pop("actions", None)
    if actions is not None and not isinstance(actions, type):
        raise TypeError(
            f"@panel: actions= must be a class (Protocol or ABC), got {type(actions).__name__}: {actions!r}"
        )

    validated_redraw_on = validate_signal_types(
        "@panel(..., redraw_on=...)", tuple(identity_kwargs.pop("redraw_on", ())), allow_empty=True
    )

    def decorator(inner_cls):
        if not issubclass(inner_cls, BasePanel):
            raise TypeError(f"@panel can only be applied to BasePanel subclasses, got {inner_cls}")

        _registry_id = identity_kwargs.pop("registry_id", None) or inner_cls.__name__

        library_identity = derive_library_identity(inner_cls)
        _registry_key = reg_key(library_identity.id, PANEL, _registry_id)

        # Remaining keys (label, icon, order, default_open, description,
        # deprecation_warning, hidden, …) splat into the identity; an unknown key
        # surfaces as a TypeError there.
        inner_cls.class_identity = PanelIdentity(
            registry_id=_registry_id,
            registry_key=_registry_key,
            editor_keys=[],
            scopes=[],
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
            action_protocol=actions,
            focus=focus,
            redraw_on=validated_redraw_on,
            **identity_kwargs,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator
