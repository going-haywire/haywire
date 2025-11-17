"""
Type Base - Base class for all Haywire data types.

This module provides the TypeBase class which serves as the foundation for all
data types in the Haywire system, both primitive type variants and custom compound types.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, TypeVar, Generic
from typing import get_type_hints

from ..data.enums import FlowType
from ..library.library_identity import LibraryIdentity
from .identity import DataPortIdentity
from .ports import PortInlet, PortOutlet


class TypeBase():
    """
    Base class for all Haywire data types.
    
    All types (primitive variants and custom compound types) inherit from this.
    Provides the interface for creating ports from types.
    
    Usage:
        # In a node:
        _ = self.add_inlet(FLOAT.as_inlet('value', default=1.0))
        _ = self.add_inlet(Temperature.as_inlet('temp', default=25.0))
        _ = self.add_inlet(MeshData.as_inlet('mesh'))
    
    Attributes (set by @type_ decorator):
        class_identity: DataPortIdentity with all type metadata
        class_library: LibraryIdentity of the library this type belongs to
    """
    
    # Set by @type_ decorator:
    class_identity: DataPortIdentity
    # Set by type registration:
    class_library: LibraryIdentity
    
    @classmethod
    def as_inlet(cls, id: str, **kwargs) -> PortInlet:
        """
        Create an inlet from this type.
        
        Args:
            id: Port identifier within the node (e.g., 'input_value')
            **kwargs: Override identity attributes or add port-specific fields
                     (default, flow_type, callback, is_pooled, etc.)
        
        Returns:
            PortInlet configured with this type's identity
        
        Example:
            FLOAT.as_inlet('value', default=1.0)
            Temperature.as_inlet('temp', default=25.0, ui={'unit': '°C'})
        """
        
        # Prepare kwargs with id and defaults
        kwargs['id'] = id
        
        # Merge identity with overrides
        port_kwargs = {
            **asdict(cls.class_identity),
            **kwargs
        }
        
        # Create the inlet
        inlet = PortInlet(**port_kwargs)
        
        # Set the library reference
        inlet.class_library = cls.class_library
        
        # Remove default from kwargs for storage (it was already used in creation)
        kwargs.pop('default', None)
        
        # Store creation recipe for serialization (if from registered type)
        if cls.class_identity.registry_key and not cls.class_identity.registry_key.startswith('default:'):
            inlet._creation_recipe = {
                'registry_key': cls.class_identity.registry_key,
                'method': 'as_inlet',
                'kwargs': kwargs
            }
        
        return inlet
    
    @classmethod
    def as_outlet(cls, id: str, **kwargs) -> PortOutlet:
        """
        Create an outlet from this type.
        
        Args:
            id: Port identifier within the node (e.g., 'output_result')
            **kwargs: Override identity attributes or add port-specific fields
        
        Returns:
            PortOutlet configured with this type's identity
        
        Example:
            FLOAT.as_outlet('result')
            MeshData.as_outlet('mesh')
        """
        
        # Prepare kwargs with id and defaults
        kwargs['id'] = id
        
        # Merge identity with overrides
        port_kwargs = {
            **asdict(cls.class_identity),
            **kwargs
        }
        
        # Create the outlet
        outlet = PortOutlet(**port_kwargs)
        
        # Set the library reference (use getattr for safety during hot-reload)
        outlet.class_library = getattr(cls, 'class_library', None)
        
        # Remove default from kwargs for storage (it was already used in creation)
        kwargs.pop('default', None)
        
        # Store creation recipe for serialization (if from registered type)
        if cls.class_identity.registry_key and not cls.class_identity.registry_key.startswith('default:'):
            outlet._creation_recipe = {
                'registry_key': cls.class_identity.registry_key,
                'method': 'as_outlet',
                'kwargs': kwargs
            }
        
        return outlet
    
    @classmethod
    def as_config(cls, id: str, **kwargs) -> PortInlet:
        """
        Create a config inlet (no visible pin) from this type.
        
        Args:
            id: Config identifier within the node
            **kwargs: Override identity attributes
        
        Returns:
            PortInlet with flow_type=NONE (no visible pin)
        
        
        Example:
            FLOAT.as_config('threshold', default=0.5)
        """
        return cls.as_inlet(id, flow_type=FlowType.NONE, **kwargs)


class PrimitiveType(TypeBase):
    """
    Base class for primitive type wrappers.
    
    Primitive types wrap Python built-in types (int, float, str, bool, bytes)
    and their variants (e.g., Temperature extends FLOAT which wraps float).
    
    **IMPORTANT**: Subclasses MUST define exactly one field named 'value' with type annotation.
    
    Valid examples:
        @dataclass
        class FLOAT(PrimitiveType):
            value: float  # ✅ Single 'value' field
        
        class Temperature(FLOAT):
            pass  # ✅ Inherits value: float from FLOAT
    
    Invalid examples:
        @dataclass  
        class BadType(PrimitiveType):
            value: int
            other: str  # ❌ ERROR: Only 'value' field allowed!
        
        class NoValue(PrimitiveType[int]):
            pass  # ❌ ERROR: Must have 'value' annotation (define or inherit)
    
    The PrimitiveType class validates this structure at import time and will
    raise TypeError if violations are detected.
    
    Usage:
        # In nodes:
        FLOAT.as_inlet('input', default=1.0)
        Temperature.as_inlet('temp', default=25.0)
    """

    