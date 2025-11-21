"""
Type system for Haywire.

This module provides infrastructure for defining and managing data types
(both primitive type variants and custom compound types) that can be passed between
nodes through inlet/outlet connections.
"""

from .base_type import BaseType
from .decorators import type
from .identity import DataPortIdentity

__all__ = ['BaseType', 'type', 'DataPortIdentity']
