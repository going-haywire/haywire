"""
Core adapter registration and exports
"""

import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from haywire.libraries.registry import AdapterRegistry

# Import all adapter classes
from .base import BaseAdapter, ConversionError
from .type_converters import (
    IntToFloatAdapter, FloatToIntAdapter,
    StringToIntAdapter, StringToFloatAdapter,
    IntToStringAdapter, FloatToStringAdapter,
    BoolToStringAdapter, StringToBoolAdapter
)


def register_core_adapters(adapter_registry: AdapterRegistry):
    """Register all core adapters with the adapter registry"""
    
    # Numeric conversions
    adapter_registry.register_adapter(
        IntToFloatAdapter.source_type,
        IntToFloatAdapter.target_type,
        IntToFloatAdapter
    )
    
    adapter_registry.register_adapter(
        FloatToIntAdapter.source_type,
        FloatToIntAdapter.target_type,
        FloatToIntAdapter
    )
    
    # String to numeric conversions
    adapter_registry.register_adapter(
        StringToIntAdapter.source_type,
        StringToIntAdapter.target_type,
        StringToIntAdapter
    )
    
    adapter_registry.register_adapter(
        StringToFloatAdapter.source_type,
        StringToFloatAdapter.target_type,
        StringToFloatAdapter
    )
    
    # Numeric to string conversions
    adapter_registry.register_adapter(
        IntToStringAdapter.source_type,
        IntToStringAdapter.target_type,
        IntToStringAdapter
    )
    
    adapter_registry.register_adapter(
        FloatToStringAdapter.source_type,
        FloatToStringAdapter.target_type,
        FloatToStringAdapter
    )
    
    # Boolean conversions
    adapter_registry.register_adapter(
        BoolToStringAdapter.source_type,
        BoolToStringAdapter.target_type,
        BoolToStringAdapter
    )
    
    adapter_registry.register_adapter(
        StringToBoolAdapter.source_type,
        StringToBoolAdapter.target_type,
        StringToBoolAdapter
    )


__all__ = [
    'BaseAdapter',
    'ConversionError',
    'IntToFloatAdapter',
    'FloatToIntAdapter', 
    'StringToIntAdapter',
    'StringToFloatAdapter',
    'IntToStringAdapter',
    'FloatToStringAdapter',
    'BoolToStringAdapter',
    'StringToBoolAdapter',
    'register_core_adapters'
]
