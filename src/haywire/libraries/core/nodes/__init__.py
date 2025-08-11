"""
Core node implementations and registration
"""

# Import core node examples
from haywire.core.node.node import is_node
from haywire.core.inventory.folder_scan import folder_scan_for_classes
from .error_node import ErrorNode

from haywire.core.inventory.base import LibraryMetadata
from haywire.core.inventory.registry.node import NodeRegistry


def register_nodes(node_registry: NodeRegistry, library_metadata: LibraryMetadata):
    """Register all core nodes with the node registry"""

    # Discover all node classes in this library
    nodes = folder_scan_for_classes(
        library_path=__path__[0],
        class_filter=is_node
    )

    nodes.remove(ErrorNode)  # Remove ErrorNode from basic nodes list

    # Register all discovered nodes
    for node_class in nodes:
        node_registry.register_node(node_class, library_metadata)

    # Register error node
    node_registry.register_error_node(ErrorNode)

__all__ = [
    'ErrorNode'
    'register_nodes'
]
