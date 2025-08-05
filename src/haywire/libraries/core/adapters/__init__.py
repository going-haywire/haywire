"""
Core adapter registration and exports
"""

from haywire.core.registry.registry import AdapterRegistry

# Import all adapter classes
from .type_converters import (
    IntToFloatAdapter
)

def register_core_adapters(adapter_registry: AdapterRegistry):
    """Register all core adapters with the adapter registry"""
    
    # Numeric conversions
    adapter_registry.register_adapter(
        IntToFloatAdapter.source_type,
        IntToFloatAdapter.target_type,
        IntToFloatAdapter
    )
    

__all__ = [
    'IntToFloatAdapter',
    'register_core_adapters'
]
