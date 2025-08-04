"""
Core node implementations and registration
"""

import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

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
