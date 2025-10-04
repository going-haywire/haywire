"""
Error handling utilities package.
"""

from .detailed_error import (
    ErrorContext,
    DetailedError,
    analyze_exception,
    create_detailed_exception,
    log_detailed_error
)

__all__ = [
    'ErrorContext',
    'DetailedError',
    'analyze_exception',
    'create_detailed_exception',
    'log_detailed_error'
]