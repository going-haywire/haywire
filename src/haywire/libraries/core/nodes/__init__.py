"""
Core node implementations and registration
"""

# Import core node examples
from haywire.core.inventory.library import BaseLibrary
from haywire.core.node.base_node import is_node
from haywire.core.inventory.folder_scan_for_classes import folder_scan_for_classes
from .error_node import ErrorNode

from haywire.core.inventory.registry.node_reg import NodeRegistry


def register_nodes(library: BaseLibrary):
    """Register all core nodes with the node registry"""

    # Discover all node classes in this library
    nodes = folder_scan_for_classes(
        library_path=__path__[0],
        library=library,
        class_filter=is_node
    )

    reg: NodeRegistry = library.get_registry(NodeRegistry)
    if reg:
        # Register all discovered nodes (including ErrorNode)
        for node_class in nodes:
            reg._register(node_class, library.identity)

__all__ = [
    'ErrorNode',
    'register_nodes'
]
