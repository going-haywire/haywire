"""
Core node implementations and registration
"""

# Import core node examples
from haywire.core.registry.auto_discover import auto_discover_classes, is_node
from .error_node import ErrorNode

from haywire.core.registry.base import LibraryMetadata
from haywire.core.registry.registry import NodeRegistry


def register_nodes(node_registry: NodeRegistry, library_metadata: LibraryMetadata):
    """Register all core nodes with the node registry"""

    # Discover all node classes in this library
    nodes = auto_discover_classes(
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
