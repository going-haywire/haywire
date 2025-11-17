"""
Error handling utilities package.
"""

from .haywire_exception import HaywireException
from .primitive_type_error import PrimitiveTypeDefinitionError
from .detailed_error import (
    ErrorContext,
    analyze_exception,
    log_detailed_error
)

from .custom_exception import (
    CustomException
)

__all__ = [
    'ErrorContext',
    'HaywireException',
    'analyze_exception',
    'log_detailed_error',
    'CustomException',
    'primitive_type_error'
]