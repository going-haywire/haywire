"""
Test nodes for the test library
"""

# Import the node system base class
from haywire.core.node.node import is_node
from haywire.core.inventory.folder_scan import folder_scan_for_classes
from haywire.core.inventory.base import LibraryMetadata
from haywire.core.inventory.registry.node import NodeRegistry
from haywire.core.inventory.utils import camel_to_dot_case

def register_nodes(node_registry: NodeRegistry, library_metadata: LibraryMetadata):
    """Register test nodes with the node registry"""

    # Discover all node classes in this library
    nodes = folder_scan_for_classes(
        library_path=__path__[0],
        metadata=library_metadata,
        class_filter=is_node
    )

    # Register all discovered nodes
    for node_class in nodes:
        node_registry.register_node(node_class, library_metadata)

__all__ = [
    'register_nodes'
]
