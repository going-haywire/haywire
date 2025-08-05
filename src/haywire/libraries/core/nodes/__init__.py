"""
Core node implementations and registration
"""

# Import core node examples
from .basic_nodes import ConstantNode, DisplayNode

def register_core_nodes(node_registry):
    """Register all core nodes with the node registry"""
    
    # Register basic nodes
    node_registry.register_node(ConstantNode)
    node_registry.register_node(DisplayNode)


__all__ = [
    'ConstantNode',
    'DisplayNode', 
    'register_core_nodes'
]
