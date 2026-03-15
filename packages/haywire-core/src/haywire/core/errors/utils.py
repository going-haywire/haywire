"""
Error handling utilities for Haywire.

This module is maintained for backward compatibility.
New code should use HaywireException methods directly.
"""

from .haywire_exception import HaywireException, ErrorSeverity

__all__ = ['HaywireException', 'ErrorSeverity']