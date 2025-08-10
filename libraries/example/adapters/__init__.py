"""
Test adapters for the test library

This module now includes both adapters and data type definitions (merged from data/ folder).
"""

from haywire.core.registry.auto_discover import auto_discover_classes, is_adapter
from haywire.core.registry.base import LibraryMetadata
from haywire.core.registry.registry import AdapterRegistry

# Data type definitions (merged from data/ folder)
from haywire.core.registry.utils import camel_to_dot_case

# Importing adapters
from .example_adapters import FloatToTemperatureAdapter, TemperatureToFloatAdapter

def register_adapters(adapter_registry: AdapterRegistry, library_metadata: LibraryMetadata):
    """Register test adapters with the adapter registry using self-registering pattern"""
    # List of adapter classes to register (self-registering pattern)

    adapters = auto_discover_classes(
        library_path=__path__[0],
        class_filter=is_adapter
    )

    # Register all discovered adapters
    for adapter_class in adapters:
        print(f"Test-Registering adapter: '{adapter_class.__name__}' as :'{camel_to_dot_case(adapter_class.__name__)}'")
        #renderers_registry.register_renderer(adapter_class, library_metadata)

    adapters = [
        FloatToTemperatureAdapter,
        TemperatureToFloatAdapter,
    ]
    
    # Register each adapter using self-registration
    for adapter_class in adapters:
        adapter_registry.register_adapter(adapter_class)
    
__all__ = [
    # Adapters
    'FloatToTemperatureAdapter',
    'TemperatureToFloatAdapter',
    'register_adapters'
]
