# packages/haywire-core/src/haywire/ui/editor_framework/decorator.py
"""
@editor decorator for marking classes as Haywire editor types.

Sets class_identity on the class. Does NOT register the class —
registration happens when the library calls add_folder() in
register_components(), following the same pattern as @renderer and @widget.

For built-in framework editors, registration is bootstrapped directly
in the DI provider via register_builtin_editors().
"""

from typing import Optional, Union

from haywire.core.library.utils import EDITOR, derive_library_identity, reg_key

from .base import BaseEditor
from .identity import EditorIdentity, OpenBehavior


def editor(
    *,
    label: Optional[str] = None,
    description: str = "",
    icon: str = "extension",
    default_slot: str = "main",
    opens: Union[OpenBehavior, str] = OpenBehavior.REQUIRED,
    order: int = 100,
    registry_id: Optional[str] = None,
):
    """
    Decorator to mark a class as an editor type.

    Always invoked with parentheses — `@editor(...)` or `@editor()`. The
    bare `@editor` form (no parens) is not supported.

    Sets class_identity on the class. Does NOT register the class —
    registration happens when the library calls add_folder() in
    register_components(), following the same pattern as @renderer and @widget.

    For built-in framework editors, registration is bootstrapped directly
    in the DI provider via register_builtin_editors().

    Args:
        label: Human-readable display name. Defaults to class name.
        icon: Material Design icon name. Defaults to 'extension'.
        default_slot: Which slot this editor belongs in by default.
            One of: 'left', 'right', 'main', 'bottom'. Defaults to 'main'.
        opens: Instance-creation behavior. One of 'required', 'on_context',
            'on_payload'. Defaults to 'required'. Any value is permitted on
            any default_slot — choosing a UX-sensible pairing is up to the
            editor author.
        order: Sort priority within a slot (lower = earlier in the bar).
            Defaults to 100. Editors with equal order fall back to
            registration order.
        description: Human-readable description.
        registry_id: Unique ID for this editor, e.g. 'graph_editor'.
            Defaults to the class name if not provided.

    Usage:
        @editor(
            label='Graph Editor',
            icon='account_tree',
            default_slot='main',
            opens='on_payload',
            description='Visual node graph editor',
        )
        class GraphEditor(BaseEditor):
            ...
    """

    def decorator(inner_cls):
        if not issubclass(inner_cls, BaseEditor):
            raise TypeError(f"@editor can only be applied to BaseEditor subclasses, got {inner_cls}")

        # Coerce string to enum; raises ValueError at class-definition time on typo.
        opens_enum = OpenBehavior(opens) if isinstance(opens, str) else opens

        _registry_id = registry_id or inner_cls.__name__
        _label = label or inner_cls.__name__

        library_identity = derive_library_identity(inner_cls)
        _registry_key = reg_key(library_identity.id, EDITOR, _registry_id)

        inner_cls.class_identity = EditorIdentity(
            registry_id=_registry_id,
            registry_key=_registry_key,
            label=_label,
            icon=icon,
            default_slot=default_slot,
            opens=opens_enum,
            order=order,
            description=description,
            class_name=inner_cls.__name__,
            module=inner_cls.__module__,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator
