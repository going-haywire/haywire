"""
Custom type system for Haywire.

This module provides infrastructure for defining and managing custom data types
that can be passed between nodes through inlet/outlet connections.
"""

from .base_type import CustomTypeIdentity, custom_type

__all__ = ['CustomTypeIdentity', 'custom_type']
