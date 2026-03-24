# packages/haywire-core/src/haywire/ui/panel/decorator.py
"""
@panel decorator for marking classes as Haywire panel types.

Sets class_identity on the class. Does NOT register the class —
registration happens when the library calls add_folder() in
register_components(), following the same pattern as @renderer and @widget.
"""

from typing import Optional, Union

from haywire.core.library.utils import derive_library_identity, reg_key

from .base import BasePanel
from .identity import PanelIdentity


def panel(
    cls=None,
    /,
    *,
    registry_id: Optional[str] = None,
    editor: str,
    scope: Union[str, list[str]],
    label: Optional[str] = None,
    icon: Optional[str] = None,
    order: int = 100,
    default_open: bool = True,
    description: str = "",
):
    """
    Decorator to mark a class as a panel.

    Sets class_identity on the class. Does NOT register the class —
    registration happens when the library calls add_folder() in
    register_components(), following the same pattern as @renderer and @widget.

    Args:
        registry_id:  Unique ID for this panel, e.g. 'node_transform'.
                      Defaults to the class name if not provided.
        editor:       Registry key of the editor this panel belongs to,
                      e.g. 'properties'.
        scope:        Scope ID or list of scope IDs this panel appears under,
                      e.g. 'node' or ['my_lib', 'node'].
        label:        Human-readable display label. Defaults to class name.
        icon:         Optional Material Design icon name.
        order:        Sort priority (lower = higher in the panel list). Default 100.
        default_open: Whether the panel starts expanded. Defaults to True.
        description:  Human-readable description.

    Usage:
        @panel(
            registry_id='node_transform',
            editor='properties',
            scope='node',
            label='Transform',
            icon='open_with',
            order=10,
        )
        class TransformPanel(BasePanel):
            @classmethod
            def poll(cls, ctx):
                return ctx.active_node is not None

            def draw(self, ctx, layout):
                layout.label(f"Node: {ctx.active_node.node.identity.label}")
    """

    def decorator(inner_cls):
        if not issubclass(inner_cls, BasePanel):
            raise TypeError(f"@panel can only be applied to BasePanel subclasses, got {inner_cls}")

        _registry_id = registry_id or inner_cls.__name__
        _label = label or inner_cls.__name__
        _scope = [scope] if isinstance(scope, str) else list(scope)

        library_identity = derive_library_identity(inner_cls)
        library_id = library_identity.id if library_identity else None
        _registry_key = reg_key(library_id, "panel", _registry_id)

        inner_cls.class_identity = PanelIdentity(
            registry_id=_registry_id,
            editor_key=editor,
            scope=_scope,
            label=_label,
            icon=icon,
            order=order,
            default_open=default_open,
            description=description,
            registry_key=_registry_key,
        )
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator if cls is None else decorator(cls)
