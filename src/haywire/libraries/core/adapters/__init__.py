"""
Core adapter registration and exports

This module now includes both adapters and core data type definitions (merged from data/ folder).
"""

from haywire.core.adapter.base import is_adapter
from haywire.core.inventory.registry.adapter import AdapterRegistry
from haywire.core.inventory.folder_scan import folder_scan_for_classes
from haywire.core.inventory.registry.library import LibraryMetadata

# --- Factory functions for creating DataFieldSpec instances ---
#
#  By default you would put the factory functions for 
#   creating DataFieldSpec instances here:
#
# INT = specs_factory(
#         id='INT', 
#         label='Integer', 
#         description='Integer data type',
#         type=DataType.INT,
#         category=DataCategory.SCALAR,
#         widget='core.number',
#     )
#
# But for convenience reasons, the factory functions for core data specs are located
# 
# -> haywire.core.data.__init__
#
# this way, third party libraries can reference them for their own adaptors.


def register_adapters(adapter_registry: AdapterRegistry, library_metadata: LibraryMetadata):
    """Register all core adapters with the adapter registry"""
    
    # Discover all adapter classes in this library
    adapters = folder_scan_for_classes(
        library_path=__path__[0],
        class_filter=is_adapter
    )

    # Register all discovered adapters
    for adapter_class in adapters:
        adapter_registry.register_adapter(adapter_class, library_metadata)

__all__ = [
    # Data types (merged from data/ folder)
    'register_adapters'
]
