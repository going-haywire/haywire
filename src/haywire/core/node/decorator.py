from haywire.core.library.utils import derive_library_identity, reg_key
from haywire.core.node.base import BaseNode, NodeIdentity


from typing import Callable, Type, TypeVar, Union

# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar('T')

def node(cls: Type[T] = None, /, **kwargs) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a Haywire node.

    Accepts any NodeIdentity field as a keyword argument. Common arguments include:

    Args:
        registry_id (str, optional): Unique identifier for the node within its library.
            Defaults to class name if not provided.
        label (str, optional): Human-readable display name for the node.
            Defaults to class name if not provided.
        description (str, optional): Detailed description of what the node does.
            Defaults to empty string.
        search_tags (list[str], optional): Tags for searching/filtering nodes in UI.
            Defaults to empty list.
        menu (str, optional): Menu category path (e.g., 'math/arithmetic', 'io/files').
            Defaults to 'misc/custom'.
        help_md (str, optional): Markdown help content displayed in node help panel.
            Defaults to None.
        help_url (str, optional): URL to external help documentation.
            Defaults to 'https://haywire.io/docs/node-help'.
        deprecation_warning (str, optional): Deprecation warning message for the node.
            Defaults to empty string.
        _is_error (bool, optional): Whether this node handles error cases.
            Defaults to False. Only one error node can be registered. 
        _error_priority (int, optional): Priority of this error node when multiple are registered.
            If multiple error nodes are registered, 
            the one with the higher _error_priority will override the previous ones.

    Any other keyword arguments will be passed through to the NodeIdentity constructor.
    See the NodeIdentity dataclass for the complete list of available fields.

    Usage:
        # Minimal usage - uses class name for registry_id and label
        @node
        class MyNode(BaseNode): ...

        # Common customization
        @node(label="Custom Node", description="Does custom things")
        class MyNode(BaseNode): ...

        # Full customization
        @node(
            registry_id="my_custom_node",
            label="My Custom Node", 
            description="Performs custom calculations",
            search_tags=["custom", "math", "utility"],
            menu="custom/math",
            help_md="## Custom Node\n\nThis node does...",
            _is_error=False
        )
        class CustomNode(BaseNode): ...

        # Error handling node
        @node(_is_error=True, label="Error Handler", menu="system/errors")
        class ErrorNode(BaseNode): ...
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseNode):
            raise TypeError(f"@node can only be applied to BaseNode subclasses, got {inner_cls}")

        # Set defaults from class name if not provided
        kwargs.setdefault('registry_id', inner_cls.__name__)
        kwargs.setdefault('label', inner_cls.__name__)

        # Get library identity (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)

        # Auto-derive registry_key
        library_id = library_identity.id if library_identity else None
        kwargs['registry_key'] = reg_key(library_id, 'node', kwargs['registry_id'])

        # Create and attach identity and library
        inner_cls.class_identity = NodeIdentity(**kwargs)
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator if cls is None else decorator(cls)