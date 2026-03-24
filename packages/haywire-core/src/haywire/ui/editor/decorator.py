# packages/haywire-core/src/haywire/ui/editor_framework/decorator.py
"""
@editor decorator for marking classes as Haywire editor types.

Sets class_identity on the class. Does NOT register the class —
registration happens when the library calls add_folder() in
register_components(), following the same pattern as @renderer and @widget.

For built-in framework editors, registration is bootstrapped directly
in the DI provider via register_builtin_editors().
"""

from typing import Optional

from haywire.core.library.utils import derive_library_identity, reg_key

from .base import BaseEditor
from .identity import EditorIdentity


def editor(
    cls=None,
    /,
    *,
    registry_id: Optional[str] = None,
    label: Optional[str] = None,
    icon: str = "extension",
    default_area: str = "middle",
    description: str = "",
):
    """
    Decorator to mark a class as an editor type.

    Sets class_identity on the class. Does NOT register the class —
    registration happens when the library calls add_folder() in
    register_components(), following the same pattern as @renderer and @widget.

    For built-in framework editors, registration is bootstrapped directly
    in the DI provider via register_builtin_editors().

    Args:
        registry_id: Unique ID for this editor, e.g. 'graph_editor'.
            Defaults to the class name if not provided.
        label: Human-readable display name. Defaults to class name.
        icon: Material Design icon name. Defaults to 'extension'.
        default_area: Which area this editor belongs in by default.
            One of: 'left', 'middle', 'right', 'bottom'. Defaults to 'middle'.
        description: Human-readable description.

    Usage:
        @editor(
            registry_id='graph_editor',
            label='Graph Editor',
            icon='account_tree',
            default_area='middle',
            description='Visual node graph editor',
        )
        class GraphEditor(BaseEditor):
            ...
    """

    def decorator(inner_cls):
        if not issubclass(inner_cls, BaseEditor):
            raise TypeError(f"@editor can only be applied to BaseEditor subclasses, got {inner_cls}")

        _registry_id = registry_id or inner_cls.__name__
        _label = label or inner_cls.__name__

        library_identity = derive_library_identity(inner_cls)
        library_id = library_identity.id if library_identity else None
        _registry_key = reg_key(library_id, "editor", _registry_id)

        inner_cls.class_identity = EditorIdentity(
            registry_id=_registry_id,
            label=_label,
            icon=icon,
            default_area=default_area,
            description=description,
            registry_key=_registry_key,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator if cls is None else decorator(cls)
