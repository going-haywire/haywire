"""
Error handling utilities for Haywire.

This module is maintained for backward compatibility.
New code should use HaywireException methods directly.
"""

from .haywire_exception import HaywireException, ErrorSeverity
from .custom_exception import CustomException

__all__ = ['HaywireException', 'ErrorSeverity', 'CustomException']