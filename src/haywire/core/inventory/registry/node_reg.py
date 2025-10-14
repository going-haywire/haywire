# No typing imports needed for current functionality

from typing import TypeVar, Optional, Union

from haywire.core.node.exceptions import NodeDiscoveryError
from haywire.core.node.dataclasses import NodeErrorInfo
from ..library_identity import LibraryIdentity
from haywire.core.node.base_node import BaseNode, is_node
from ..base import BaseClassRegistry, FileChangeEvent, FileEventType, RegistryFolder
from ..utils import camel_to_dot_case, reg_key


class NodeRegistry(BaseClassRegistry):
    """Simplified registry for managing nodes using library.name:node.name keys"""
    directory_name: str = RegistryFolder.NODES.value
    class_filter = lambda self, cls: is_node(cls)  # Use the node filter

    def __init__(self):
        super().__init__()
        self._error_node: type | None = None

    def _register(self, node_cls: type[BaseNode], library_identity: LibraryIdentity):
        """
        Register a node class with library metadata.

        Sets node class attributes from library metadata and registers under
        the key format: library.name:node.name

        Args:
            node_class: The node class to register
            library_identity: Library metadata to use for setting node attributes

        Raises:
            ValueError: If a node with the same key is already registered
        """
        # Store the library metadata and registry key as class attributes 
        # This will be used as the default for new instances
        node_cls.class_library = library_identity

        # Create registry key
        registry_key = reg_key(library_identity.id, node_cls.class_identity.registry_id)

        # Check for duplicates
        if self.has(registry_key):
            raise ValueError(f"Node already registered: {registry_key}")

        # Set the registry_key in the class_identity if it exists
        if hasattr(node_cls, 'class_identity'):
            node_cls.class_identity.registry_key = registry_key

        # Check if this is an error node and register it automatically
        if hasattr(node_cls, 'class_identity') and node_cls.class_identity.is_error:
            self._error_node = node_cls
        else:
            # we only register non-error nodes in the main registry
            super()._register(registry_key, node_cls)


    def _unregister(self, name) -> type[BaseNode] | None:
        """Unregister a node by its haywire name
        Args:
            name: The name of the node to unregister
        """
        return super()._unregister(name)

    def get_error_node(self) -> type[BaseNode] | None:
        """Get the error node class"""
        return self._error_node

    def get_node_class(self, key: str) -> tuple[NodeErrorInfo | None, BaseNode.__class__]:
        """
        Get node class by registry key for graph operations.

        Args:
            key: Registry key in format "library_id:node_name"

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
