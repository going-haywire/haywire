"""
DataPort Classes - Updated to work with new DataField system

This module provides the DataPort, PortInlet, and PortOutlet classes
that integrate with the new DataField hierarchy.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from haywire.core.data.enums import FlowType
from haywire.core.types.identity import DataTypeIdentity
from haywire.core.types.interface import IType
from haywire.core.types.base import PrimitiveType, BaseType, CompoundType

# Import the new DataField classes
from haywire.core.data.fields import (
    DataField,
    PrimitiveField,
    BaseField,
    CompoundField
)

@dataclass
class DataPort(DataTypeIdentity):
    """
    Extended DataTypeIdentity with runtime port information.
    
    Adds runtime-specific fields on top of the identity:
    - id: Port identifier within the node
    - flow_type: CTRL, DATA, CALLBACK, or NONE
    - data: Runtime data field for storing values (created by type)
    - Connection state, element type, etc.
    
    Key simplification: Field is created by type.create_field(), not factory.
    
    Type tracking:
    - type_cls: The IType class (FLOAT, MeshData, ArrayType)
    - element_type_cls: For compound types, the element IType (FLOAT, MeshData)
    
    Hierarchical access:
        port.element_type_cls → FLOAT (for ArrayType[FLOAT])
        port.element_type_cls.element_type_cls → float (Python type)
    """
    
    # Port identifier within node (different from registry_id!)
    id: str = ''
    
    # Runtime data field (created by type in __post_init__)
    data: Optional[DataField] = None
    
    # Type tracking
    type_cls: type[IType] = None  # The type class (FLOAT, ArrayType, etc.)
    element_type_cls: Optional[type[IType]] = None  # For compound types, the element IType
    
    # Connection state
    is_connected: bool = False
    allow_multiple_connections: bool = False  # True for pooled inlets
    
    # Inlet-specific
    use_mode: str = 'optional'
    is_lazy: bool = False
    
    # Outlet-specific
    pipes: list = field(default_factory=list)
    
    # Internal: Store default override for field creation
    _default_override: Optional[Dict[str, Any]] = field(default=None, init=False, repr=False)
    
    def get_value(self) -> Any:
        """
        Get unwrapped value for worker convenience.
        
        Returns:
            - For PrimitiveField: Unwrapped primitive (42.0)
            - For BaseField: BaseType instance (MeshData(...))
            - For CompoundField: Container (dict, list, etc.)
            - None if no data
        """
        if not self.data:
            return None
        
        return self.data.get_value()
    
    def set_value(self, new_value: Any, source_id: str | None = None) -> None:
        """
        Set value from connection or programmatic update.
        
        Args:
            new_value: Value to set (can be IType instance or raw value)
            source_id: Source identifier (required for pooled fields)
        """
        if not self.data:
            return
        
        self.data.set_value(new_value, source_id=source_id)
    
    def __post_init__(self):
        """
        Create data field via type.
        
        Simplified - no factory! Type creates its own field.
        """
        # Skip parent's post_init for runtime ports
        
        # Create data field if needed
        if self.data is None and self.type_cls is not None:
            # Type creates its own field!
            self.data = self.type_cls.create_field(
                element_type_cls=self.element_type_cls,
                default_override=self._default_override
            )
    
    def is_pin(self) -> bool:
        """Check if this is a visible pin (not a config)"""
        return self.flow_type != FlowType.NONE.value
    
    def is_inlet(self) -> bool:
        """Check if this is an inlet"""
        return False
    
    def validate_connection_rules(
        self,
        other_port: 'DataPort'
    ) -> tuple[bool, Optional[str]]:
        """
        Validate port-level connection rules (NO type checking).
        
        This checks only port-specific rules:
        - Port connection: inlet <-> outlet
        - Connection state
        - Connection count limits
        - DataField existence
        
        Type compatibility is handled separately by AdapterFactory.
        
        Args:
            other_port: The other DataPort attempting to connect
            
        Returns:
            (is_valid, error_message)
        """
        # Check if this is an inlet (sanity check)
        if self.is_inlet() == other_port.is_inlet():
            return (False, "Cannot connect inlet to inlet or outlet to outlet")
        
        # Check connection count limits
        if (
            not self.allow_multiple_connections and 
            self.is_connected
        ):
            return (
                False, 
                f"Port '{self.id}' already connected and does not "
                f"allow multiple connections"
            )
        
        # DataFields must exist
        if not self.data:
            return (False, "Missing DataField on port '{self.id}'")

        # All port-level checks passed
        # Type compatibility will be checked via adapter chain creation
        return (True, None)
    
    def to_dict(self) -> dict:
        """
        Serialize port to dict.
        
        Uses stored creation recipe for compact serialization.
        
        Returns:
            Dict with recipe format
        """
        if hasattr(self, '_creation_recipe'):
            return {
                'type': 'recipe',
                **self._creation_recipe
            }
        
        raise NotImplementedError("Port serialization requires _creation_recipe")
    
    @classmethod
    def from_dict(cls, data: dict, type_registry) -> 'PortInlet | PortOutlet':
        """
        Deserialize port from dict.
        
        Args:
            data: Serialized port data (from to_dict())
            type_registry: TypeRegistry to look up registered types
        
        Returns:
            Reconstructed PortInlet or PortOutlet
        """
        if data.get('type') == 'recipe':
            registry_key = data['registry_key']
            method_name = data['method']
            kwargs = data['kwargs']
            
            # Get the type class from registry
            type_cls = type_registry.get_type_class(registry_key)
            if not type_cls:
                raise ValueError(f"Type '{registry_key}' not found in registry")
            
            # Handle compound types with element_type
            if 'element_type_registry_key' in kwargs:
                element_type_key = kwargs.pop('element_type_registry_key')
                element_type_cls = type_registry.get_type_class(element_type_key)
                
                # Reconstruct: CompoundType[ElementType].as_inlet(...)
                parameterized = type_cls[element_type_cls]
                method = getattr(parameterized, method_name)
            else:
                # Simple type: Type.as_inlet(...)
                method = getattr(type_cls, method_name)
            
            # Extract id
            port_id = kwargs.pop('id')
            
            # Recreate the port (field created in __post_init__)
            return method(port_id, **kwargs)
        
        else:
            raise ValueError(f"Unknown port serialization format: {data.get('type')}")


@dataclass
class PortInlet(DataPort):
    """Inlet port - can receive data from connections"""
    
    def is_inlet(self) -> bool:
        return True
    
    # __post_init__ inherited from DataPort


@dataclass
class PortOutlet(DataPort):
    """Outlet port - can send data to connections"""
    
   # __post_init__ inherited from DataPort
