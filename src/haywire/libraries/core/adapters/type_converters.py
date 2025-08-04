"""
Basic type conversion adapters
"""

from typing import Any
from .base import BaseAdapter, ConversionError

import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from haywire.core.data.enums import DataType


class IntToFloatAdapter(BaseAdapter):
    """Convert integer to float"""
    source_type = DataType.INT
    target_type = DataType.FLOAT
    
    def can_convert(self, value: Any) -> bool:
        return isinstance(value, int)
    
    def convert(self, value: Any) -> float:
        if not self.can_convert(value):
            raise ConversionError(f"Cannot convert {type(value)} to float")
        return float(value)


class FloatToIntAdapter(BaseAdapter):
    """Convert float to integer (truncates)"""
    source_type = DataType.FLOAT
    target_type = DataType.INT
    
    def can_convert(self, value: Any) -> bool:
        return isinstance(value, (float, int))
    
    def convert(self, value: Any) -> int:
        if not self.can_convert(value):
            raise ConversionError(f"Cannot convert {type(value)} to int")
        return int(value)


class StringToIntAdapter(BaseAdapter):
    """Convert string to integer"""
    source_type = DataType.STRING
    target_type = DataType.INT
    
    def can_convert(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        try:
            int(value)
            return True
        except ValueError:
            return False
    
    def convert(self, value: Any) -> int:
        if not isinstance(value, str):
            raise ConversionError(f"Cannot convert {type(value)} to int")
        try:
            return int(value)
        except ValueError:
            raise ConversionError(f"Cannot convert '{value}' to int")


class StringToFloatAdapter(BaseAdapter):
    """Convert string to float"""
    source_type = DataType.STRING
    target_type = DataType.FLOAT
    
    def can_convert(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        try:
            float(value)
            return True
        except ValueError:
            return False
    
    def convert(self, value: Any) -> float:
        if not isinstance(value, str):
            raise ConversionError(f"Cannot convert {type(value)} to float")
        try:
            return float(value)
        except ValueError:
            raise ConversionError(f"Cannot convert '{value}' to float")


class IntToStringAdapter(BaseAdapter):
    """Convert integer to string"""
    source_type = DataType.INT
    target_type = DataType.STRING
    
    def can_convert(self, value: Any) -> bool:
        return isinstance(value, int)
    
    def convert(self, value: Any) -> str:
        if not self.can_convert(value):
            raise ConversionError(f"Cannot convert {type(value)} to string")
        return str(value)


class FloatToStringAdapter(BaseAdapter):
    """Convert float to string"""
    source_type = DataType.FLOAT
    target_type = DataType.STRING
    
    def can_convert(self, value: Any) -> bool:
        return isinstance(value, (float, int))
    
    def convert(self, value: Any) -> str:
        if not self.can_convert(value):
            raise ConversionError(f"Cannot convert {type(value)} to string")
        return str(value)


class BoolToStringAdapter(BaseAdapter):
    """Convert boolean to string"""
    source_type = DataType.BOOL
    target_type = DataType.STRING
    
    def can_convert(self, value: Any) -> bool:
        return isinstance(value, bool)
    
    def convert(self, value: Any) -> str:
        if not self.can_convert(value):
            raise ConversionError(f"Cannot convert {type(value)} to string")
        return str(value).lower()


class StringToBoolAdapter(BaseAdapter):
    """Convert string to boolean"""
    source_type = DataType.STRING
    target_type = DataType.BOOL
    
    TRUE_VALUES = {'true', '1', 'yes', 'on', 'enabled'}
    FALSE_VALUES = {'false', '0', 'no', 'off', 'disabled'}
    
    def can_convert(self, value: Any) -> bool:
        if not isinstance(value, str):
            return False
        return value.lower() in (self.TRUE_VALUES | self.FALSE_VALUES)
    
    def convert(self, value: Any) -> bool:
        if not isinstance(value, str):
            raise ConversionError(f"Cannot convert {type(value)} to bool")
        
        value_lower = value.lower()
        if value_lower in self.TRUE_VALUES:
            return True
        elif value_lower in self.FALSE_VALUES:
            return False
        else:
            raise ConversionError(f"Cannot convert '{value}' to bool")
