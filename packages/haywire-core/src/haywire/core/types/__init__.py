"""
Type system for Haywire.

This module provides infrastructure for defining and managing data types
(both primitive type variants and custom compound types) that can be passed between
nodes through inlet/outlet connections.
"""

from .interface import IType
from .base import PrimitiveType, BaseType, CompoundType, WrapperType
from .decorator import type
from .identity import DataTypeIdentity
from .enums import LayoutDirection, NodeDetail, PortOrigin, PortType, Propagation, StoreStrategy
from .event import Event
from .fields import DataField, PrimitiveField, BaseField
from .port import DataPort
from .widget_model import WidgetModel
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
from .wire import WILDCARD, WireRole, WireType, get_wire_type, wire_type_of, wires_match

__all__ = [
    # Interface
    "IType",
    # Base types
    "PrimitiveType",
    "BaseType",
    "CompoundType",
    "WrapperType",
    # Decorator
    "type",
    # Identity
    "DataTypeIdentity",
    # Enums
    "LayoutDirection",
    "NodeDetail",
    "PortOrigin",
    "PortType",
    "Propagation",
    "StoreStrategy",
    # Event system
    "Event",
    # Fields
    "DataField",
    "PrimitiveField",
    "BaseField",
    # Ports and Pipes
    "DataPort",
    "WidgetModel",
    "Pipes",
    # Registry
    "TypeRegistry",
    # Wire types
    "WILDCARD",
    "WireRole",
    "WireType",
    "get_wire_type",
    "wire_type_of",
    "wires_match",
    # Specs & utilities
    "PortSpec",
    "ElementTypeSpec",
    "create_port_spec",
    "serialize_element_type",
    "normalize_and_validate_default",
    "is_cattrs_serializable",
]
