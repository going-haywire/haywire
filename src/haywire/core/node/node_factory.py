"""
Pure Node Factory utility.

This factory is a utility class that creates node instances from registry keys.
It handles hot reloading support and node tracking but does not manage graph
lifecycle or undo operations - those are handled by Graph and Actions respectively.
"""

import time
import uuid
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass
from collections import defaultdict

from .node import BaseNode
from ..graph.graph import HaywireGraph
from ..inventory.registry.node import NodeRegistry


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
        self._hot_reload_listeners: List[Callable[[str, List[str]], None]] = []
        
   
    def create_instance(self, registry_key: str, graph: HaywireGraph, 
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
            raise ValueError(f"Failed to get node class '{registry_key}': {error_info}")
        
        # Create the node instance 
        node = node_class(node_id, graph)
        
        # Set the library metadata from the class default
        if hasattr(node_class, '_default_library_metadata'):
            node.library = node_class._default_library_metadata
        
        if error_info:
            node.error_info = error_info
        
        # Set position if provided
        if position:
            node.ui_state.posX, node.ui_state.posY = position
                       
        return node
        
    def handle_hot_reload(self, registry_key: str) -> List[str]:
        """
        Handle hot reload of a node class.
        
        This method is called when the node registry detects that a node class
        has been reloaded. It notifies listeners but does not modify existing
        node instances (as per the requirement to keep hot reload separate
        from undo history).
        
        Args:
            registry_key: The registry key that was reloaded
            
        Returns:
            List of node IDs that are affected by this reload
        """
        affected_node_ids = list(self._nodes_by_registry_key.get(registry_key, set()))
        
        # Notify listeners about the hot reload
        for listener in self._hot_reload_listeners:
            listener(registry_key, affected_node_ids)
        
        return affected_node_ids
    
    def add_hot_reload_listener(self, callback: Callable[[str, List[str]], None]) -> None:
        """
        Add a callback for hot reload notifications.
        
        Args:
            callback: Function called with (registry_key, affected_node_ids)
        """
        self._hot_reload_listeners.append(callback)
    
    def remove_hot_reload_listener(self, callback: Callable[[str, List[str]], None]) -> None:
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
                label = node_class._default_library_metadata.label
                description = node_class._default_library_metadata.description
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
            else:
                label = node_class._default_library_metadata.label
                description = node_class._default_library_metadata.description
                tags = getattr(node_class, 'node_search_tags', [])

            # Search in label, description, and tags
            searchable = [
                label.lower(),
                description.lower(),
                *[tag.lower() for tag in tags]
            ]

            if any(query_lower in text for text in searchable):
                metadata = self.node_registry.get_metadata(key)
                library_name = metadata.name if metadata else 'Unknown'
                
                results.append({
                    'label': label,
                    'key': key,
                    'description': description,
                    'library': library_name
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
        if not self.node_registry.has(registry_key):
            return None
        
        node_class = self.node_registry.get(registry_key)
        metadata = self.node_registry.get_metadata(registry_key)
        
        # Use class_identity if available, fallback to old attributes
        if hasattr(node_class, 'class_identity'):
            identity = node_class.class_identity
            label = identity.label
            description = identity.description
            tags = identity.search_tags
            menu = identity.menu
        else:
            label = node_class._default_library_metadata.label
            description = node_class._default_library_metadata.description
            tags = getattr(node_class, 'node_search_tags', [])
            menu = getattr(node_class, 'node_menu', 'misc')
        
        return {
            'registry_key': registry_key,
            'label': label,
            'description': description,
            'search_tags': tags,
            'menu': menu,
            'library_name': metadata.name if metadata else None,
            'library_version': metadata.version if metadata else None,
            'class_name': node_class.__name__,
            'module': node_class.__module__
        }
