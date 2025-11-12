"""
Type system for Haywire.

This module provides infrastructure for defining and managing data types
(both type variants and custom compound types) that can be passed between
nodes through inlet/outlet connections.
"""

from .base import TypeBase
from .decorators import type_
from ..data.identity import DataPortIdentity

__all__ = ['TypeBase', 'type_', 'DataPortIdentity']
