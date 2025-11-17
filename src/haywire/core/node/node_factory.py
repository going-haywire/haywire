"""
Pure Node Factory utility.

This factory is a utility class that creates node instances from registry keys.
It handles hot reloading support and node tracking but does not manage graph
lifecycle or undo operations - those are handled by Graph and Actions respectively.
"""

import time
import uuid
import logging
from typing import Dict, List, Optional, Any, Callable, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from collections import defaultdict

from ..errors.haywire_exception import HaywireException

if TYPE_CHECKING:
    from ..graph.graph import HaywireGraph

from .base_node import BaseNode
from .node_wrapper import NodeWrapper
from ..library.registries.reg_node import NodeRegistry
from ..library.library_identity import LibraryIdentity
from ..library.hot_reload_event import LifeCycleEvent, HotReloadCallback
from ..errors import log_detailed_error


class NodeFactory:
    """
    Pure node factory utility.
    
    This factory is a utility class that creates node instances from registry keys.
    It handles hot reload tracking but does not manage graph lifecycle or undo 
    operations - those are handled by Graph and Actions respectively.
    """
    
    def __init__(self, node_registry: NodeRegistry):
        """
        Initialize the node factory.
        
        Args:
            node_registry: Registry containing node class definitions
        """
        self.node_registry = node_registry
                
        # Hot reload notification callbacks
        self._hot_reload_listeners: List[HotReloadCallback] = []
        
        # Register this factory as a customer callback for node registry hot reloads
        self.node_registry.add_customer_callback(self._on_node_reloaded)
        
   
    def create_instance(self, registry_key: str, graph: 'HaywireGraph', 
                       node_id: Optional[str] = None, position: Optional[Tuple[float, float]] = None) -> BaseNode:
        """
        Pure utility method to create a node instance.
        
        This method only creates the node instance and tracks it for hot reload.
        It does not add the node to any graph or interact with undo systems.
        
        Args:
            registry_key: Key in the node registry
            graph: Parent graph for the node
            node_id: Optional custom node ID (generated if not provided)
            position: Optional (x, y) position for the node
            
        Returns:
            The created node instance
            
        Raises:
            ValueError: If registry key is not found or node creation fails
        """
        # Generate node ID if not provided
        if node_id is None:
            node_id = self._generate_node_id()
        
        # Get node class from registry
        error_info, node_class = self.node_registry.get_node_class(registry_key)
        if error_info is not None:
            logging.error(f"NodeFactory: Failed to get node class for key '{registry_key}': {error_info}")
            if node_class is None:  
                raise ValueError(f"Failed to get class '{registry_key}': {error_info}")
        
        # Create the node instance with detailed error handling
        try:
            node = node_class(node_id, graph)
        except Exception as e:
            # Create detailed error with context about the node instantiation
            error = log_detailed_error(
                exception=e,
                operation="instantiate node",
                module_name=getattr(node_class, '__module__', None),
                registry_key=registry_key,
                class_name=node_class.__name__,
                library_identity=node_class.class_library,
                message=f"Failed to instantiate node '{registry_key}'"
            )
            raise HaywireException(error)
                
        if error_info:
            node.error_info = error_info
        
        # Set position if provided
        if position:
            node.ui_state.posX, node.ui_state.posY = position
                       
        return node
    
    def create_wrapper(self, registry_key: str, node_id: Optional[str] = None, 
                      position: Optional[Tuple[float, float]] = None) -> NodeWrapper:
        """
        Create a NodeWrapper instance with deferred node initialization.
        
        This is the primary method for creating nodes in the NodeWrapper-based system.
        
        Args:
            registry_key: Key in the node registry
            node_id: Optional custom node ID (generated if not provided)
            position: Optional (x, y) position for the node
            
        Returns:
            The created NodeWrapper instance (uninitialized)
        """
        # Generate node ID if not provided
        if node_id is None:
            node_id = self._generate_node_id()
            
        # Create wrapper (uninitialized)
        wrapper = NodeWrapper(
            node_id=node_id,
            registry_key=registry_key,
            node_factory=self,
            initial_position=position
        )
        
        return wrapper
    
    def _on_node_reloaded(self, event: LifeCycleEvent) -> None:
        """
        Customer callback for node hot reload events.
        
        This is called by the NodeRegistry when a node class is reloaded, added, or removed.
        It forwards the notification to all registered hot reload listeners (typically NodeWrappers).
        
        Args:
            event: The hot reload event with complete context
        """
        logging.info(
            f"NodeFactory: Node {event.event_type.value} - {event.registry_key} "
            f"from library '{event.library_identity.label}'"
        )
        
        # Forward to all hot reload listeners (NodeWrappers, etc.)
        for listener in self._hot_reload_listeners:
            listener(event)
        
    def handle_hot_reload(self, registry_key: str) -> None:
        """
        Handle hot reload of a node class.
        
        This method is called when the node registry detects that a node class
        has been reloaded. It notifies all listeners, and the NodeWrappers will
        determine if they need to migrate based on their registry_key.
        
        Args:
            registry_key: The registry key that was reloaded
        """        
        # This method is kept for backward compatibility but may not be used
        # with the new event system. Events are now passed directly.
        logging.warning(
            f"NodeFactory.handle_hot_reload called with registry_key={registry_key}. "
            f"This method is deprecated in favor of event-based hot reload."
        )
    
    def add_hot_reload_listener(self, callback: HotReloadCallback) -> None:
        """
        Add a callback for hot reload notifications.
        
        Args:
            callback: Function called with HotReloadEvent
        """
        self._hot_reload_listeners.append(callback)
    
    def remove_hot_reload_listener(self, callback: HotReloadCallback) -> None:
        """
        Remove a hot reload notification callback.
        
        Args:
            callback: The callback to remove
        """
        if callback in self._hot_reload_listeners:
            self._hot_reload_listeners.remove(callback)
    
    # Private helper methods
    
    def _generate_node_id(self) -> str:
        """Generate a unique node ID."""
        return f"node_{uuid.uuid4().hex[:8]}"
                
    
    # ============================================================================
    # Node Discovery and UI Services (moved from NodeRegistry)
    # ============================================================================
    
    def get_menu_structure(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get nodes organized by menu path for UI building.

        Returns:
            Dictionary mapping menu paths to lists of node info dicts
        """
        menu = {}

        for key in self.node_registry.list_names():
            node_class = self.node_registry.get(key)
            
            # Use class_identity if available, fallback to old attributes
            if hasattr(node_class, 'class_identity'):
                identity = node_class.class_identity
                menu_path = identity.menu
                label = identity.label
                description = identity.description
                tags = identity.search_tags
            else:
                menu_path = getattr(node_class, 'node_menu', 'misc')
                label = node_class.class_library.label
                description = node_class.class_library.description
                tags = getattr(node_class, 'node_search_tags', [])

            if menu_path not in menu:
                menu[menu_path] = []

            menu[menu_path].append({
                'label': label,           # Display name
                'key': key,               # Registry key
                'description': description,
                'tags': tags
            })

        return menu

    def search_nodes(self, query: str) -> List[Dict[str, str]]:
        """
        Search for nodes matching a query string.

        Args:
            query: Search query string

        Returns:
            List of matching node info dicts
        """
        results = []
        query_lower = query.lower()

        for key in self.node_registry.list_names():
            node_class = self.node_registry.get(key)

            # Use class_identity if available, fallback to old attributes
            if hasattr(node_class, 'class_identity'):
                identity = node_class.class_identity
                label = identity.label
                description = identity.description
                tags = identity.search_tags

            # Search in label, description, and tags
            searchable = [
                label.lower(),
                description.lower(),
                *[tag.lower() for tag in tags]
            ]

            if any(query_lower in text for text in searchable):
                library = node_class.class_library
                library_label = library.label if library else 'Unknown'

                results.append({
                    'label': label,
                    'key': key,
                    'description': description,
                    'library': library_label
                })

        return results

    def list_all_nodes(self) -> List[str]:
        """
        Get list of all registered node registry keys.

        Returns:
            List of all registry keys
        """
        return self.node_registry.list_names()

    def get_node_info(self, registry_key: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific node.

        Args:
            registry_key: Registry key of the node

        Returns:
            Dictionary with node information or None if not found
        """

        node_class = self.node_registry.get(registry_key)
        if node_class is not None:
            library_identity = node_class.class_library
            
            # Use class_identity if available, fallback to old attributes
            if hasattr(node_class, 'class_identity'):
                identity = node_class.class_identity
                label = identity.label
                description = identity.description
                tags = identity.search_tags
                menu = identity.menu
            else:
                label = node_class.class_library.label
                description = node_class.class_library.description
                tags = getattr(node_class, 'node_search_tags', [])
                menu = getattr(node_class, 'node_menu', 'misc')
            
            return {
                'registry_key': registry_key,
                'label': label,
                'description': description,
                'search_tags': tags,
                'menu': menu,
                'library_label': library_identity.label if library_identity else None,
                'library_version': library_identity.version if library_identity else None,
                'class_name': node_class.__name__,
                'module': node_class.__module__
            }
        
        return None
