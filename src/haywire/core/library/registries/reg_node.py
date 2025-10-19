# No typing imports needed for current functionality

import inspect
from typing import Type, TypeVar, Optional, Union

from ...node.exceptions import NodeDiscoveryError
from ...node.dataclasses import NodeErrorInfo
from ..library_identity import LibraryIdentity
from ...node.base_node import BaseNode
from ..class_registry import BaseClassRegistry
from ..utils import reg_key

class NodeRegistry(BaseClassRegistry):
    """Simplified registry for managing nodes using library.name:node.name keys"""

    def __init__(self):
        super().__init__()
        self._error_node: type | None = None

    def _class_filter(self, cls):
        """Check if a class is a valid Haywire node class."""
        try:
            return (inspect.isclass(cls) and
                    issubclass(cls, BaseNode) and
                    cls != BaseNode and
                    hasattr(cls, 'class_identity'))
        except TypeError:
            return False

    def _register_class(self, node_cls: type[BaseNode], library_identity: LibraryIdentity) -> str | None:
        """
        Register a node class with library metadata.

        Sets node class attributes from library metadata and registers under
        the key format: library.name:node.name

        Args:
            node_class: The node class to register
            library_identity: Library metadata to use for setting node attributes
        Returns:
            str: The haywire registry_key of the registered node.

        Raises:
            ValueError: If a node with the same key is already registered
        """
        # Create registry key
        registry_key = reg_key(library_identity.id, node_cls.class_identity.registry_id)

        # Check if this is an error node and register it automatically
        if node_cls.class_identity.is_error:
            self._error_node = node_cls
            return None
        else:
            # we only register non-error nodes in the main registry
            return super()._register(registry_key, node_cls, library_identity)


    def _unregister_class(self, registry_key) -> type[BaseNode] | None:
        """Unregister a node by its registry_key
        Args:
            registry_key: The registry_key of the node to unregister

        Returns:
            type[BaseNode] | None: The unregistered node class or None if not found
        """
        return super()._unregister(registry_key)

    def get_error_node(self) -> type[BaseNode] | None:
        """Get the error node class"""
        return self._error_node

    def get_node_class(self, key: str) -> tuple[NodeErrorInfo | None, Type[BaseNode] | None]:
        """
        Get node class by registry key for graph operations.

        Args:
            key: Registry key in format "library_id:node_name"

        Returns:
            Tuple of (success: bool, node_class: type)
            - success: True if the requested node was found, False if error node was returned
            - node_class: Either the requested node class or the error node class
        """
        node_class = self._classes.get(key)
        creationerror = None
        if node_class is None:
            # Return error node if registered
            creationerror = NodeErrorInfo(
                error='Node Not Found',
                error_message='The requested node could not be found in the registry. Serving Error Node.'
            )
            creationerror.add_note(f"Library: {key.split(':')[0]}")
            creationerror.add_note(f"Node: {key.split(':')[-1]}")
            if self._error_node:
                node_class = self._error_node
        return creationerror, node_class
