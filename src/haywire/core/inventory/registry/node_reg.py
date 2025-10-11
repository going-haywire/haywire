# No typing imports needed for current functionality

from typing import Callable, Type, TypeVar, Optional, Union
from haywire.core.node.node import BaseNode, NodeDiscoveryError, NodeErrorInfo, NodeIdentity, is_node
from ..base import BaseClassRegistry, FileChangeEvent, FileEventType, LibraryMetadata, RegistryFolder
from ..utils import camel_to_dot_case, reg_key

T = TypeVar('T')

def node(cls: Type[T] = None, /, *,
         registry_id: Optional[str] = None,
         label: Optional[str] = None,
         description: Optional[str] = None,
         search_tags: Optional[list[str]] = None,
         menu: str = 'misc/custom',
         help_md: Optional[str] = None,
         help_url: str = 'https://haywire.io/docs/node-help',
         is_error: bool = False) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a Haywire node.
    
    Args:
        registry_id: Unique identifier for the node
        label: Human-readable label
        description: Detailed description
        search_tags: Tags for searching/filtering
        menu: Menu category path
        help_md: Markdown help content
        help_url: URL to help documentation
        is_error: Whether this node should handle error cases

    Usage:
        @node
        class MyNode(BaseNode): ...

        @node(label="Custom Node", description="Does custom things")
        class MyNode(BaseNode): ...
        
        @node(is_error=True, label="Error Node")
        class ErrorNode(BaseNode): ...
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseNode):
            raise TypeError(f"@node can only be applied to BaseNode subclasses, got {inner_cls}")

        # Use class name as fallback for label and registry_id
        final_label = label or inner_cls.__name__
        final_registry_id = registry_id or inner_cls.__name__.lower()

        inner_cls.class_identity = NodeIdentity(
            registry_id=final_registry_id,
            label=final_label,
            description=description or '',
            search_tags=search_tags or [],
            menu=menu,
            help_md=help_md,
            help_url=help_url,
            is_error=is_error
        )
        
        return inner_cls

    if cls is None:
        return decorator
    return decorator(cls)


class NodeRegistry(BaseClassRegistry):
    """Simplified registry for managing nodes using library.name:node.name keys"""
    directory_name: str = RegistryFolder.NODES.value
    class_filter = lambda self, cls: is_node(cls)  # Use the node filter

    def __init__(self):
        super().__init__()
        self._error_node: type | None = None

    def register_node(self, node_cls: type[BaseNode], library_metadata: LibraryMetadata):
        """
        Register a node class with library metadata.

        Sets node class attributes from library metadata and registers under
        the key format: library.name:node.name

        Args:
            node_class: The node class to register
            library_metadata: Library metadata to use for setting node attributes

        Raises:
            ValueError: If a node with the same key is already registered
        """
        # Create registry key
        registry_key = reg_key(library_metadata.name, node_cls.class_identity.registry_id)

        # Check for duplicates
        if self.has(registry_key):
            raise ValueError(f"Node already registered: {registry_key}")

        # Store the library metadata and registry key as class attributes 
        # This will be used as the default for new instances
        node_cls.class_library = library_metadata

        # Set the registry_key in the class_identity if it exists
        if hasattr(node_cls, 'class_identity'):
            node_cls.class_identity.registry_key = registry_key

        self._register(registry_key, node_cls, library_metadata)

    def unregister_node(self, name) -> type[BaseNode] | None:
        """Unregister a node by its haywire name
        Args:
            name: The name of the node to unregister
        """
        return super()._unregister(name)

    def register_error_node(self, node_class: type[BaseNode]):
        """Register the error node class"""
        self._error_node = node_class

    def get_error_node(self) -> type[BaseNode] | None:
        """Get the error node class"""
        return self._error_node

    def get_node_class(self, key: str) -> tuple[NodeErrorInfo | None, BaseNode.__class__]:
        """
        Get node class by registry key for graph operations.

        Args:
            key: Registry key in format "library_name:node_name"

        Returns:
            Tuple of (success: bool, node_class: type)
            - success: True if the requested node was found, False if error node was returned
            - node_class: Either the requested node class or the error node class

        Raises:
            NodeDiscoveryError: If node is not found and no error node is registered
        """
        node_class = self.get(key)
        if node_class is None:
            # Return error node if registered
            if self._error_node:
                creationerror = NodeErrorInfo(
                    error='Node Not Found',
                    error_message='The requested node could not be found in the registry.'
                )
                creationerror.add_note(f"Library: {key.split(':')[0]}")
                creationerror.add_note(f"Node: {key.split(':')[-1]}")
                return creationerror, self._error_node
            # Otherwise raise error
            raise NodeDiscoveryError(f"Node not found: {key}. No error node registered.")
        return None, node_class

    def handle_module_change(self, module: str, event: FileChangeEvent, metadata: LibraryMetadata):
        """
        Handle file change events for node modules.

        Args:
            event: FileChangeEvent containing file path and event type
        """
        if event.event_type == FileEventType.CREATED:
            added_classes = self._on_creation(module)
            if added_classes:
                for cls_name in added_classes:
                    self.register_node(cls_name, metadata)
        elif event.event_type == FileEventType.MODIFIED:
            added_classes, removed_classes = self._on_change(module)
            if removed_classes:
                for cls_name in removed_classes:
                    self.unregister_node(cls_name)
            if added_classes:
                for cls_name in added_classes:
                    self.register_node(cls_name, metadata)
        elif event.event_type == FileEventType.DELETED:
            removed_classes = self._on_delete(module)
            if removed_classes:
                for cls_name in removed_classes:
                    self.unregister_node(cls_name)
