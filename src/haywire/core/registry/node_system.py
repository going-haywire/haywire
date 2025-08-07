"""
Simplified node registry system for the Haywire library system.

This module contains a simplified node registry that uses library metadata
as the single source of truth and eliminates complex version checking.
"""

from typing import Dict, List, Optional, Any
from .base import BaseRegistry, LibraryMetadata

# Import core node classes
from haywire.core.node.node import HaywireNode, NodeDiscoveryError


class NodeRegistry(BaseRegistry):
    """Simplified registry for managing nodes using library_name:node_name keys"""
    
    def __init__(self):
        super().__init__()
    
    def register_node(self, node_class: type, library_metadata: LibraryMetadata):
        """
        Register a node class with library metadata.
        
        Sets node class attributes from library metadata and registers under
        the key format: library_name:node_name
        
        Args:
            node_class: The node class to register
            library_metadata: Library metadata to use for setting node attributes
            
        Raises:
            ValueError: If a node with the same key is already registered
        """
        # Set library-derived attributes on the node class
        setattr(node_class, 'library_name', library_metadata.name)
        setattr(node_class, 'library_version', library_metadata.version)
        setattr(node_class, 'library_url', library_metadata.url)
        setattr(node_class, 'library_help_url', library_metadata.help_url)
        setattr(node_class, 'library_author', library_metadata.author)
        setattr(node_class, 'library_author_url', library_metadata.author_url)


        # Create registry key
        key = f"{library_metadata.name}:{node_class.node_name}"
        
        # Check for duplicates
        if self.has(key):
            raise ValueError(f"Node already registered: {key}")
        
        # Register with metadata
        metadata = {
            'library_name': library_metadata.name,
            'library_metadata': library_metadata,
            'node_name': node_class.node_name,
            'node_version': library_metadata.version,
            'node_author': library_metadata.author,
            'node_url': library_metadata.url,
            'node_help_url': library_metadata.help_url
        }
        
        self.register(key, node_class, metadata)
    
    def get_node_class(self, key: str) -> type:
        """
        Get node class by registry key for graph operations.
        
        Args:
            key: Registry key in format "library_name:node_name"
            
        Returns:
            Node class
            
        Raises:
            NodeDiscoveryError: If node is not found
        """
        node_class = self.get(key)
        if node_class is None:
            raise NodeDiscoveryError(f"Node not found: {key}")
        return node_class
    
    def get_menu_structure(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get nodes organized by menu path for UI building.
        
        Returns:
            Dictionary mapping menu paths to lists of node info dicts
        """
        menu = {}
        
        for key in self.list_names():
            node_class = self.get(key)
            menu_path = getattr(node_class, 'node_menu', 'misc')
            
            if menu_path not in menu:
                menu[menu_path] = []
            
            menu[menu_path].append({
                'label': node_class.node_label,           # Display name
                'key': key,                               # Registry key
                'description': node_class.node_description,
                'tags': getattr(node_class, 'node_search_tags', [])
            })
        
        return menu
    
    def search_nodes(self, query: str) -> List[Dict[str, str]]:
        """
        Search nodes by name, description, or tags.
        
        Args:
            query: Search query string
            
        Returns:
            List of matching node info dicts
        """
        results = []
        query_lower = query.lower()
        
        for key in self.list_names():
            node_class = self.get(key)
            
            # Search in label, description, and tags
            searchable = [
                node_class.node_label.lower(),
                node_class.node_description.lower(),
                *[tag.lower() for tag in getattr(node_class, 'node_search_tags', [])]
            ]
            
            if any(query_lower in text for text in searchable):
                results.append({
                    'label': node_class.node_label,
                    'key': key,
                    'description': node_class.node_description,
                    'library': self.get_metadata(key)['library_name']
                })
        
        return results
    
    def get_nodes_by_library(self, library_name: str) -> List[Dict[str, str]]:
        """
        Get all nodes from a specific library.
        
        Args:
            library_name: Name of the library
            
        Returns:
            List of node info dicts from the specified library
        """
        results = []
        
        for key in self.list_names():
            metadata = self.get_metadata(key)
            if metadata and metadata.get('library_name') == library_name:
                node_class = self.get(key)
                results.append({
                    'label': node_class.node_label,
                    'key': key,
                    'description': node_class.node_description,
                    'node_name': node_class.node_name
                })
        
        return results
    
    def list_libraries(self) -> List[str]:
        """
        Get list of all libraries that have registered nodes.
        
        Returns:
            List of unique library names
        """
        libraries = set()
        
        for key in self.list_names():
            metadata = self.get_metadata(key)
            if metadata:
                libraries.add(metadata['library_name'])
        
        return sorted(list(libraries))


# Convenience functions for backward compatibility and ease of use
def create_node_from_key(registry: NodeRegistry, key: str, node_id: str, graph) -> HaywireNode:
    """
    Create a node instance from a registry key.
    
    Args:
        registry: The node registry
        key: Registry key in format "library_name:node_name"
        node_id: Unique ID for the node instance
        graph: Graph instance the node belongs to
        
    Returns:
        Node instance
    """
    node_class = registry.get_node_class(key)
    return node_class(node_id, graph)


def serialize_node_metadata(node: HaywireNode) -> Dict[str, Any]:
    """
    Serialize node metadata for saving (simplified version).
    
    Args:
        node: Node instance to serialize
        
    Returns:
        Dictionary containing node metadata
    """
    return {
        'node_id': node.node_id,
        'registry_key': f"{node.node_library_name}:{node.node_name}",
        'ui_properties': {
            'posX': getattr(node, 'ui_posX', 0),
            'posY': getattr(node, 'ui_posY', 0),
            'width': getattr(node, 'ui_width', 200),
            'height': getattr(node, 'ui_height', 100),
            'is_collapsed': getattr(node, 'ui_is_collapsed', False),
            'is_condensed': getattr(node, 'ui_is_condensed', False),
            'is_pinned': getattr(node, 'ui_is_pinned', False),
            'custom_color': getattr(node, 'ui_custom_color', None)
        }
    }


# ============================================================================
# Error Node (specific to discovery system)
# ============================================================================


class ErrorNode(HaywireNode):
    """Special node to represent nodes that couldn't be loaded properly"""
    
    node_label = 'Error Node'
    node_description = 'Placeholder for node that could not be loaded'
    node_name = 'ERROR_NODE'
    node_search_tags = ['error', 'system', 'placeholder']
    node_menu = 'system/error'
    
    def __init__(self, node_id, graph, error_info: Dict[str, Any], 
                 original_inlets=None, original_outlets=None):
        super().__init__(node_id, graph)
        
        # Store error information
        self.error_info = error_info
        self.original_node_name = error_info.get('node_name', 'Unknown')
        self.original_package_name = error_info.get('node_package', 'Unknown')
        self.original_version = error_info.get('node_version', 'Unknown')
        self.error_message = error_info.get('error_message', 'Unknown error')
        
        # Preserve original inlet/outlet structure for connections
        self.original_inlets = original_inlets or []
        self.original_outlets = original_outlets or []
        
        # Override display properties
        self.node_display_name = f"ERROR: {self.original_node_name}"
        self.ui_default_color = '#FF0000'  # Red for error
