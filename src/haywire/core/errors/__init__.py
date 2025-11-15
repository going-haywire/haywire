"""
Error handling utilities package.
"""

from .PrimitiveTypeDefinitionError import PrimitiveTypeDefinitionError
from .detailed_error import (
    ErrorContext,
    DetailedError,
    analyze_exception,
    log_detailed_error
)

from .haywire_exception import (
    HaywireException
)

__all__ = [
    'ErrorContext',
    'DetailedError',
    'analyze_exception',
    'log_detailed_error',
    'HaywireException',
    'PrimitiveTypeDefinitionError'
]