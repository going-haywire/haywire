"""
Core node implementations and registration
"""

# Import core node examples
from .basic_nodes import TestNodeOne

from haywire.core.registry.base import LibraryMetadata
from haywire.core.registry.node_system import NodeRegistry


def register_nodes(node_registry: NodeRegistry, library_metadata: LibraryMetadata):
    """Register all core nodes with the node registry"""
    
    # Register basic nodes
    node_registry.register_node(TestNodeOne, library_metadata)


__all__ = [
    'TestNodeOne',
    'register_nodes'
]
