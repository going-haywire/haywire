"""
Core node implementations and registration
"""

# Import core node examples
from .basic_nodes import TestNodeOne

def register_core_nodes(node_registry):
    """Register all core nodes with the node registry"""
    
    # Register basic nodes
    node_registry.register_node(TestNodeOne)


__all__ = [
    'TestNodeOne',
    'register_core_nodes'
]
