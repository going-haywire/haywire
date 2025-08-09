"""
Test nodes for the test library
"""

# Import the node system base class
from haywire.core.registry.base import LibraryMetadata
from haywire.core.registry.registry import NodeRegistry
from .display_node import DisplayNode

def register_nodes(node_registry: NodeRegistry, library_metadata: LibraryMetadata):
    """Register test nodes with the node registry"""
    node_registry.register_node(DisplayNode, library_metadata)


__all__ = [
    'DisplayNode',
    'register_nodes'
]
