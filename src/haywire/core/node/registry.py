# No typing imports needed for current functionality

import inspect
import logging

from haywire.core.library.utils import get_registry_id_from_key

from ...core.registry.lifecycle_event import LifeCycleEvent
from ..registry.base import BaseRegistry
from ..library.identity import LibraryIdentity
from . import BaseNode

class NodeRegistry(BaseRegistry):
    """registry for managing nodes using library.name:node:node.name keys"""

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

    def _register_class(
        self, node_cls: type[BaseNode], library_identity: LibraryIdentity
    ) -> str | None:
        """
        Register a node class with library metadata.

        Uses the registry_key that was set by the @node decorator during class definition.

        Args:
            node_class: The node class to register
            library_identity: Library metadata to use for setting node attributes
        Returns:
            str: The haywire registry_key of the registered node.

        Raises:
            ValueError: If a node with the same key is already registered
        """
        # Use registry_key that was set by the decorator
        registry_key = node_cls.class_identity.registry_key

        # Check if this is an error node and register it automatically
        if node_cls.class_identity._is_error:
            if self._error_node is not None:
                if (
                    node_cls.class_identity._error_priority 
                    > self._error_node.class_identity._error_priority
                ):
                    logging.warning(
                        f"Overriding already registered error node: "
                        f"'{self._error_node.class_identity.registry_key}'."
                        f" with : '{node_cls.class_identity.registry_key}'"
                        f" due to higher _error_priority "
                        f"({node_cls.class_identity._error_priority} > "
                        f"{self._error_node.class_identity._error_priority})"
                    )
                    self._error_node = node_cls
            else:
                self._error_node = node_cls

        return super()._register(registry_key, node_cls, library_identity)


    def _unregister_class(self, registry_key) -> type[BaseNode] | None:
        """Unregister a node by its registry_key
        Args:
            registry_key: The registry_key of the node to unregister

        Returns:
            type[BaseNode] | None: The unregistered node class or None if not found
        """
        if self.get(registry_key) == self._error_node:
            self._error_node = None
            logging.warning(
                f"Error node '{registry_key}' unregistered, "
                f"no error node left in registry"
            )
    
        return super()._unregister(registry_key)

    def _get_error_node(self) -> type[BaseNode] | None:
        """Get the error node class"""
        return self._error_node

    def get_node_lastevent(self, key: str) -> LifeCycleEvent | None:
        """Get the last lifecycle event for a node by its registry key."""
        return self._regkey_to_last_lifecycle_event.get(key)
    
    def get_alternate_node_registry_keys(self, registry_key: str) -> list[str]:
        """
        Get alternate node registry keys for a given node registry key.
        It takes the regitry_id from the registry_key and finds all nodes
        with the same registry_id but from differtent libraries.

        Args:
            registry_key (str): The registry key of the node to find alternates for.    
        Returns:
            list[str]: A list of alternate node registry keys.
        """
        registry_id = get_registry_id_from_key(registry_key)
        alternates = []
        for key in self._classes.keys():
            if get_registry_id_from_key(key) == registry_id and key != registry_key:
                alternates.append(key)
        return alternates

