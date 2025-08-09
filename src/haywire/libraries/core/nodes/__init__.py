"""
Core node implementations and registration
"""

# Import core node examples
from .basic_nodes import TestNodeOne
from .error_node import ErrorNode

from haywire.core.registry.base import LibraryMetadata
from haywire.core.registry.registry import NodeRegistry


def register_nodes(node_registry: NodeRegistry, library_metadata: LibraryMetadata):
    """Register all core nodes with the node registry"""

    # Register error node
    node_registry.register_error_node(ErrorNode)

    # Register basic nodes
    node_registry.register_node(TestNodeOne, library_metadata)
    
__all__ = [
    'TestNodeOne',
    'ErrorNode'
    'register_nodes'
]
