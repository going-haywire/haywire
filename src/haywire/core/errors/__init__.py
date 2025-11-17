"""
Error handling utilities package.
"""

from .haywire_error import HaywireError
from .haywire_exception import HaywireException
from .primitive_type_error import PrimitiveTypeDefinitionError
from .utils import (
    generate_haywire_error,
    log_detailed_error
)

from .custom_exception import (
    CustomException
)

__all__ = [
    'haywire_error',
    'HaywireException',
    'generate_haywire_error',
    'log_detailed_error',
    'CustomException',
    'primitive_type_error'
]