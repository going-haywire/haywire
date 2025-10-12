"""
Test nodes for the test library
"""

# Import the node system base class
from haywire.core.inventory.library import BaseLibrary
from haywire.core.node.base_node import is_node
from haywire.core.inventory.folder_scan_for_classes import folder_scan_for_classes
from haywire.core.inventory.registry.node_reg import NodeRegistry
from haywire.core.inventory.utils import camel_to_dot_case

def register_nodes(library: BaseLibrary):
    """Register nodes with the node registry"""

    # Discover all node classes in this library
    nodes = folder_scan_for_classes(
        library_path=__path__[0],
        library=library,
        class_filter=is_node
    )

    reg = library.get_registry(NodeRegistry)
    if reg:
        # Register all discovered nodes
        for node_class in nodes:
            reg.register_node(node_class, library.identity)

__all__ = [
    'register_nodes'
]
