"""
Simplified node registry system for the Haywire library system.

This module contains a simplified node registry that uses library metadata
as the single source of truth and eliminates complex version checking.
"""

from typing import Dict, List, Optional, Any

# Import core node classes
from haywire.core.node.node import BaseNode

# Convenience functions for backward compatibility and ease of use
def create_node_from_key(registry: BaseNode, key: str, node_id: str, graph) -> BaseNode:
    """
    Create a node instance from a registry key.
    
    Args:
        registry: The node registry
        key: Registry key in format "library.name:node.name"
        node_id: Unique ID for the node instance
        graph: Graph instance the node belongs to
        
    Returns:
        Node instance
    """
    node_class = registry.get_node_class(key)
    return node_class(node_id, graph)


def serialize_node_metadata(node: BaseNode) -> Dict[str, Any]:
    """
    Serialize node metadata for saving (simplified version).
    
    Args:
        node: Node instance to serialize
        
    Returns:
        Dictionary containing node metadata
    """
    return {
        'node_id': node.node_id,
        'registry_key': f"{node.registry_key}",
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

