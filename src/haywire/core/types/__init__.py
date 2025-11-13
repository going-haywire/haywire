"""
Type system for Haywire.

This module provides infrastructure for defining and managing data types
(both primitive type variants and custom compound types) that can be passed between
nodes through inlet/outlet connections.
"""

from .base import TypeBase
from .decorators import primitive_type, compound_type
from .identity import DataPortIdentity

__all__ = ['TypeBase', 'primitive_type', 'compound_type', 'DataPortIdentity']
