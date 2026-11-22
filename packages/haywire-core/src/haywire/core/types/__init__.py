"""
Type system for Haywire.

This module provides infrastructure for defining and managing data types
(both primitive type variants and custom compound types) that can be passed between
nodes through inlet/outlet connections.
"""

from __future__ import annotations

from .base import BaseType, CompoundType, PrimitiveType, WrapperType
from .decorator import type
from .enums import LayoutDirection, NodeDetail, PortOrigin, PortType, Propagation, StoreStrategy
from .event import Event
from .fields import BaseField, DataField, Drained, PrimitiveField
from .identity import DataTypeIdentity
from .interface import IType
from .pipe import Pipes
from .port import DataPort
from .registry import TypeRegistry
from .utils import (
    ElementTypeSpec,
    PortSpec,
    create_port_spec,
    is_cattrs_serializable,
    normalize_and_validate_default,
    serialize_element_type,
)
from .widget_model import WidgetModel
from .wire import (
    WILDCARD,
    ArrowAt,
    WireRole,
    WireType,
    declaring_type_of,
    get_wire_type,
    wire_type_of,
    wires_match,
)

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
    "Drained",
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
    "ArrowAt",
    "WireRole",
    "WireType",
    "get_wire_type",
    "declaring_type_of",
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
