"""
Core adapter registration and exports

This module now includes both adapters and core data type definitions (merged from data/ folder).
"""

from haywire.core.registry.auto_discover import auto_discover_classes, is_adapter
from haywire.core.registry.registry import AdapterRegistry, LibraryMetadata

# Data type definitions (merged from data/ folder)
from haywire.core.data.enums import DataType, DataCategory
from haywire.core.data.specs import specs_factory
from haywire.core.registry.utils import camel_to_dot_case

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

# Import all adapter classes
from .basic_adapters import (
    IntToFloatAdapter
)

def register_adapters(adapter_registry: AdapterRegistry, library_metadata: LibraryMetadata):
    """Register all core adapters with the adapter registry"""
    
    adapters = auto_discover_classes(
        library_path=__path__[0],
        class_filter=is_adapter
    )

    # Register all discovered adapters
    for adapter_class in adapters:
        print(f"Test-Registering adapter: '{adapter_class.__name__}' as :'{camel_to_dot_case(adapter_class.__name__)}'")
        #renderers_registry.register_renderer(adapter_class, library_metadata)


    # List of adapter classes to register (self-registering pattern)
    adapters = [
        IntToFloatAdapter,
    ]
    
    # Register each adapter using self-registration
    for adapter_class in adapters:
        adapter_registry.register_adapter(adapter_class)

__all__ = [
    # Data types (merged from data/ folder)
    'DataType',
    'DataCategory', 
    'specs_factory',
    # Factory functions
    'INT',
    'FLOAT',
    'STRING',
    # Adapters
    'IntToFloatAdapter',
    'register_adapters'
]
