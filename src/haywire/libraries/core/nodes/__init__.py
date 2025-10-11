"""
Core node implementations and registration
"""

# Import core node examples
from haywire.core.node.node import is_node
from haywire.core.inventory.folder_scan import folder_scan_for_classes
from .error_node import ErrorNode

from haywire.core.inventory.registry.node_reg import NodeRegistry


def register_nodes(library):
    """Register all core nodes with the node registry"""

    # Discover all node classes in this library
    nodes = folder_scan_for_classes(
        library_path=__path__[0],
        metadata=library.metadata,
        class_filter=is_node
    )

    nodes.remove(ErrorNode)  # Remove ErrorNode from basic nodes list

    reg = library.get_registry(NodeRegistry)
    if reg:
        # Register all discovered nodes
        for node_class in nodes:
            reg.register_node(node_class, library.metadata)

        # Register error node
        reg.register_error_node(ErrorNode)

__all__ = [
    'ErrorNode',
    'register_nodes'
]
