"""
Core adapter registration and exports

This module now includes both adapters and core data type definitions (merged from data/ folder).
"""

from haywire.core.registry.registry import AdapterRegistry

# Data type definitions (merged from data/ folder)
from haywire.core.data.enums import DataType, DataCategory
from haywire.core.data.specs import specs_factory

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
from .type_converters import (
    IntToFloatAdapter
)

def register_adapters(adapter_registry: AdapterRegistry):
    """Register all core adapters with the adapter registry"""
    
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
