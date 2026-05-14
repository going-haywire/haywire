# packages/haywire-core/src/haywire/ui/panel/decorator.py
"""
@panel decorator for marking classes as Haywire panel types.

Sets class_identity on the class. Does NOT register the class —
registration happens when the library calls add_folder() in
register_components(), following the same pattern as @renderer and @widget.

Usage::

    @panel(action=PropertiesEditorActions, focus=NodeFocus, label='Transform')
    class TransformPanel(BasePanel):
        def draw(self, ctx, layout, actions):
            ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from haywire.core.library.utils import derive_library_identity, reg_key
from haywire.core.session.handlers import validate_event_types

from .focus import Focus
from .identity import PanelIdentity
from .base import BasePanel

if TYPE_CHECKING:
    from haywire.core.session.events import ContextSignal


def panel(
    *,
    action: Optional[type] = None,
    focus: Optional[type] = None,
    label: Optional[str] = None,
    icon: Optional[str] = None,
    order: int = 100,
    default_open: bool = True,
    description: str = "",
    registry_id: Optional[str] = None,
    redraw_on: Tuple[type["ContextSignal"], ...] = (),
):
    """Decorator to mark a class as a panel.

    Always invoked with parentheses — `@panel(...)`. The bare `@panel`
    form (no parens) is not supported; `action=`, `focus=`, and `label=`
    are required.

    Sets class_identity on the class. Does NOT register the class —
    registration happens when the library calls add_folder() in
    register_components(), following the same pattern as @renderer and @widget.

    Args:
        action: Protocol or ABC class declaring the actions this panel calls.
                Must be a class.
        focus:  Focus subclass that discriminates which session states this
                panel applies to. Must subclass Focus.
        label:  Human-readable display label. Required.
        icon:   Optional Material Design icon name.
        order:  Sort priority (lower = higher in the panel list). Default 100.
        default_open: Whether the panel starts expanded. Defaults to True.
        description:  Human-readable description.
        registry_id:  Unique ID for this panel, e.g. 'node_transform'.
                      Defaults to the class name if not provided.
        redraw_on:    Tuple of ContextSignal subclasses the panel wants its
                      host editor to redraw on. Panels do not have their own
                      handler dispatch — when one of these events publishes,
                      the editor redraws and the panel re-mounts. Empty tuple
                      (the default) means the panel contributes no
                      subscriptions. The framework uses this to compute the
                      editor's effective subscription set; dispatch wiring
                      lands in a later step of the event-bus redesign.

    Raises:
        ValueError: If action=, focus=, or label= is missing.
        TypeError:  If action is not a class, focus is not a Focus subclass,
                    the decorated class is not a BasePanel subclass, or any
                    redraw_on= entry is not a ContextSignal subclass.
    """
    if action is None:
        raise ValueError("@panel requires action= (Protocol or ABC class).")
    if focus is None:
        raise ValueError("@panel requires focus= (Focus subclass).")
    if not isinstance(action, type):
        raise TypeError(
            f"@panel: action= must be a class (Protocol or ABC), got {type(action).__name__}: {action!r}"
        )
    if not (isinstance(focus, type) and issubclass(focus, Focus)):
        raise TypeError(f"@panel: focus= must be a Focus subclass, got {focus!r}")
    if label is None:
        raise ValueError("@panel requires label=.")

    validated_redraw_on = validate_event_types(
        "@panel(..., redraw_on=...)", tuple(redraw_on), allow_empty=True
    )

    def decorator(inner_cls):
        if not issubclass(inner_cls, BasePanel):
            raise TypeError(f"@panel can only be applied to BasePanel subclasses, got {inner_cls}")

        _registry_id = registry_id or inner_cls.__name__

        library_identity = derive_library_identity(inner_cls)
        _registry_key = reg_key(library_identity.id, "panel", _registry_id)

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
            action=action,
            focus=focus,
            redraw_on=validated_redraw_on,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator
