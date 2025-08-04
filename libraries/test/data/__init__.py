"""
Test data definitions for the test library
"""

import sys
import os

# Add project paths for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from haywire.core.data.enums import DataType, DataCategory
from haywire.core.data.specs import create_data_field_factory

# Custom data type for testing
TEMPERATURE = create_data_field_factory(DataType.FLOAT, DataCategory.SCALAR)

__all__ = [
    'TEMPERATURE'
]
