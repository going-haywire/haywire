"""
Test nodes for the test library
"""

# Import the node system base class
from haywire.core.registry.auto_discover import auto_discover_classes, is_node
from haywire.core.registry.base import LibraryMetadata
from haywire.core.registry.registry import NodeRegistry
from haywire.core.registry.utils import camel_to_dot_case
from .display_node import DisplayNode

def register_nodes(node_registry: NodeRegistry, library_metadata: LibraryMetadata):
    """Register test nodes with the node registry"""

    nodes = auto_discover_classes(
        library_path=__path__[0],
        class_filter=is_node
    )

    # Register all discovered nodes
    for node_class in nodes:
        print(f"Test-Registering node: '{node_class.__name__}' as :'{camel_to_dot_case(node_class.__name__)}'")
        #node_registry.register_node(node_class, library_metadata)

    nodes = [
        DisplayNode,
    ]

    for node_class in nodes:
        node_registry.register_node(node_class, library_metadata)

__all__ = [
    'DisplayNode',
    'register_nodes'
]
