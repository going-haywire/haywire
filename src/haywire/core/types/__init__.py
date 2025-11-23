"""
Type system for Haywire.

This module provides infrastructure for defining and managing data types
(both primitive type variants and custom compound types) that can be passed between
nodes through inlet/outlet connections.
"""

from .base import BaseType
from .decorator import type
from .identity import DataTypeIdentity

__all__ = ['BaseType', 'type', 'DataTypeIdentity']
