"""
Core node implementations and registration
"""

# Import core node examples
from haywire.core.inventory.library import BaseLibrary
from haywire.core.inventory.registry.node_reg import NodeRegistry

def register_nodes(library: BaseLibrary):
    """Register all core nodes with the node registry"""

    library.add_folder_to_registry(__path__[0], NodeRegistry)

__all__ = [
    'register_nodes'
]
