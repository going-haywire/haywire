"""
Error handling utilities package.

The unified HaywireException class replaces the old HaywireError/HaywireException split.
For backward compatibility, HaywireError is kept but should not be used in new code.

Use HaywireException.from_exception() or HaywireException.create() directly.
"""

from .haywire_exception import HaywireException, ErrorSeverity
from .primitive_type_error import PrimitiveTypeDefinitionError
from .custom_exception import CustomException

__all__ = [
    'HaywireException',       # Use this
    'ErrorSeverity',
    'CustomException',
    'PrimitiveTypeDefinitionError'
]