"""
Test nodes for the test library
"""

# Import the node system base class
from haywire.core.node.node import HaywireNode
from .display_node import DisplayNode


def register_test_nodes(node_registry):
    """Register test nodes with the node registry"""
    node_registry.register_node(DisplayNode)


__all__ = [
    'DisplayNode',
    'register_test_nodes'
]
