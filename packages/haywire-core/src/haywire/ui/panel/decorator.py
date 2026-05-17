# packages/haywire-core/src/haywire/ui/panel/decorator.py
"""
@panel decorator for marking classes as Haywire panel types.

Sets class_identity on the class. Does NOT register the class —
registration happens when the library calls add_folder() in
register_components(), following the same pattern as @renderer and @widget.

Usage::

    @panel(actions=NodeContextActions, focus=NodeFocus, label='Delete Node')
    class DeleteNodePanel(BasePanel):
        actions: NodeContextActions   # for type-checker visibility on self.actions

        def draw(self, ctx, layout):
            self.actions.delete_node(...)

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

from typing import Any, Optional, Tuple

from haywire.core.library.utils import PANEL, derive_library_identity, reg_key
from haywire.core.session.handlers import validate_signal_types

from .focus import Focus
from .identity import PanelIdentity
from .base import BasePanel


def panel(
    *,
    actions: Optional[type] = None,
    focus: Optional[type] = None,
    label: Optional[str] = None,
    icon: Optional[str] = None,
    order: int = 100,
    default_open: bool = True,
    description: str = "",
    registry_id: Optional[str] = None,
    redraw_on: Tuple[Any, ...] = (),
):
    """Decorator to mark a class as a panel.

    Always invoked with parentheses — `@panel(...)`. ``focus=`` and
    ``label=`` are required.

    Args:
        actions: Protocol/ABC class declaring the host contract this panel
                 mounts against. Optional — display panels omit it. When
                 set, the framework injects the host instance into
                 ``panel.actions`` at mount time (only if the host
                 structurally satisfies the protocol).
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

    Raises:
        ValueError: If focus= or label= is missing.
        TypeError:  If focus is not a Focus subclass, actions= (when set)
                    is not a class, the decorated class is not a BasePanel
                    subclass, or any redraw_on= entry is not a Signal subclass.
    """
    if focus is None:
        raise ValueError("@panel requires focus= (Focus subclass).")
    if not (isinstance(focus, type) and issubclass(focus, Focus)):
        raise TypeError(f"@panel: focus= must be a Focus subclass, got {focus!r}")
    if label is None:
        raise ValueError("@panel requires label=.")
    if actions is not None and not isinstance(actions, type):
        raise TypeError(
            f"@panel: actions= must be a class (Protocol or ABC), got {type(actions).__name__}: {actions!r}"
        )

    validated_redraw_on = validate_signal_types(
        "@panel(..., redraw_on=...)", tuple(redraw_on), allow_empty=True
    )

    def decorator(inner_cls):
        if not issubclass(inner_cls, BasePanel):
            raise TypeError(f"@panel can only be applied to BasePanel subclasses, got {inner_cls}")

        _registry_id = registry_id or inner_cls.__name__

        library_identity = derive_library_identity(inner_cls)
        _registry_key = reg_key(library_identity.id, PANEL, _registry_id)

        inner_cls.class_identity = PanelIdentity(
            registry_id=_registry_id,
            registry_key=_registry_key,
            label=label,
            editor_keys=[],
            scopes=[],
            icon=icon,
            order=order,
            default_open=default_open,
            description=description,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
            action_protocol=actions,
            focus=focus,
            redraw_on=validated_redraw_on,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator
