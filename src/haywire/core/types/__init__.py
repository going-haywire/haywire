"""
Type system for Haywire.

This module provides infrastructure for defining and managing data types
(both primitive type variants and custom compound types) that can be passed between
nodes through inlet/outlet connections.
"""

from .interface import IType
from .base import PrimitiveType, BaseType, CompoundType
from .decorator import type
from .identity import DataTypeIdentity
from .enums import FlowType, PortType
from .event import Event
from .fields import DataField, PrimitiveField, BaseField
from .port import DataPort
from .pipe import Pipes
from .registry import TypeRegistry
from .utils import (
    PortSpec,
    ElementTypeSpec,
    create_port_spec,
    serialize_element_type,
    normalize_and_validate_default,
    is_cattrs_serializable,
)

__all__ = [
    # Interface
    "IType",
    # Base types
    "PrimitiveType",
    "BaseType",
    "CompoundType",
    # Decorator
    "type",
    # Identity
    "DataTypeIdentity",
    # Enums
    "FlowType",
    "PortType",
    # Event system
    "Event",
    # Fields
    "DataField",
    "PrimitiveField",
    "BaseField",
    # Ports and Pipes
    "DataPort",
    "Pipes",
    # Registry
    "TypeRegistry",
    # Specs & utilities
    "PortSpec",
    "ElementTypeSpec",
    "create_port_spec",
    "serialize_element_type",
    "normalize_and_validate_default",
    "is_cattrs_serializable",
]
