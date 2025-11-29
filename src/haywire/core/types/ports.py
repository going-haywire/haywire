"""
DataPort Classes - Updated to work with new DataField system

This module provides the DataPort, PortInlet, and PortOutlet classes
that integrate with the new DataField hierarchy.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from haywire.core.data.enums import FlowType
from haywire.core.types.base import PrimitiveType
from haywire.core.types.identity import DataTypeIdentity
from haywire.core.types.interface import IType
from haywire.core.types.base import BaseType

# Import the new DataField classes
from haywire.core.data.fields import (
    DataField,
    PrimitiveField,
    ComplexField,
    PooledField,
    ArrayField
)


@dataclass
class DataPort(DataTypeIdentity):
    """
    Extended DataTypeIdentity with runtime port information.
    
    Adds runtime-specific fields on top of the identity:
    - id: Port identifier within the node
    - flow_type: CTRL, DATA, CALLBACK, or NONE
    - data: Runtime data field for storing values
    - Connection state, pooling, callbacks, etc.
    """
    
    # Port identifier within node (different from registry_id!)
    id: str = ''
    
    # Runtime fields
    data: Optional[DataField] = None
    
    # Pin-specific (unused for Config/Property)
    is_connected: bool = False
    
    # Inlet-specific (unused for Outlet/Config/Property)
    is_pooled: bool = False
    use_mode: str = 'optional'
    is_lazy: bool = False
    
    # Outlet-specific (unused for Inlet/Config/Property)
    pipes: list = field(default_factory=list)
    
    # Type tracking for arrays and pooled fields
    element_type_cls: Optional[type[IType]] = None
    
    def get_value(self) -> Any:
        """
        Get unwrapped value for worker convenience.
        
        Returns:
            - For PrimitiveField: Unwrapped primitive (42.0, "hello")
            - For ComplexField: BaseType instance (MeshData(...))
            - For PooledField: Dict[str, T] or List[T]
            - For ArrayField: List[T]
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
        """Skip parent's post_init for runtime ports"""
        # Note: We skip DataTypeIdentity's __post_init__() because runtime
        # ports already have their fields explicitly set
        pass
    
    def is_pin(self) -> bool:
        """Check if this is a visible pin (not a config)"""
        return self.flow_type != FlowType.NONE.value
    
    def is_inlet(self) -> bool:
        """Check if this is an inlet"""
        return False
    
    def to_dict(self) -> dict:
        """
        Serialize port to dict.
        
        If the port was created via Type.as_inlet()/as_outlet(), uses the stored
        creation recipe for compact serialization.
        
        Returns:
            Dict with recipe format: {type: 'recipe', registry_key, method, kwargs}
        """
        # If port has a creation recipe, use that for serialization
        if hasattr(self, '_creation_recipe'):
            return {
                'type': 'recipe',
                **self._creation_recipe
            }
        
        # Fallback: should not happen in normal usage
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
        
        Raises:
            ValueError: If registry_key not found or data format invalid
        """
        if data.get('type') == 'recipe':
            # Recipe format - recreate via Type.as_inlet()/as_outlet()
            registry_key = data['registry_key']
            method_name = data['method']
            kwargs = data['kwargs']
            
            # Get the type class from registry
            type_cls = type_registry.get_type_class(registry_key)
            if not type_cls:
                raise ValueError(f"Type '{registry_key}' not found in registry")
            
            # Get the method (as_inlet or as_outlet) directly from type class
            method = getattr(type_cls, method_name)
            
            # Extract id (required positional arg)
            port_id = kwargs.pop('id')
            
            # Recreate the port by calling the method
            return method(port_id, **kwargs)
        
        else:
            raise ValueError(f"Unknown port serialization format: {data.get('type')}")


class DataFieldFactory:
    """Factory for creating DataField instances based on type and configuration"""
    
    @staticmethod
    def create(
        type_cls: type[IType],
        is_pooled: bool = False,
        is_array: bool = False,
        element_type_cls: Optional[type[IType]] = None,
        default_override: Optional[Dict[str, Any]] = None
    ) -> DataField:
        """
        Create appropriate DataField instance.
        
        Args:
            type_cls: Type class (FLOAT, MeshData, etc.)
            is_pooled: Whether this is a pooled field
            is_array: Whether this is an array field
            element_type_cls: Element type for pooled/array fields
            default_override: Override default kwargs
        
        Returns:
            Appropriate DataField subclass instance
        """
        # Pooled field
        if is_pooled:
            if not element_type_cls:
                raise ValueError("Pooled fields require element_type_cls")
            return PooledField(element_type_cls=element_type_cls)
        
        # Array field
        if is_array:
            if not element_type_cls:
                raise ValueError("Array fields require element_type_cls")
            
            # Get default kwargs from type or use override
            default_kwargs = default_override or getattr(type_cls.class_identity, 'default', {})
            
            return ArrayField(
                element_type_cls=element_type_cls,
                default_kwargs=default_kwargs
            )
        
        # Get default kwargs from type or use override
        default_kwargs = default_override or getattr(type_cls.class_identity, 'default', {})
        
        # Primitive field
        if issubclass(type_cls, PrimitiveType):
            return PrimitiveField(
                type_cls=type_cls,
                default_kwargs=default_kwargs
            )
        
        # Complex field
        if issubclass(type_cls, BaseType):
            return ComplexField(
                type_cls=type_cls,
                default_kwargs=default_kwargs
            )
        
        raise TypeError(f"Cannot create DataField for type {type_cls}")


@dataclass
class PortInlet(DataPort):
    """Inlet port - can receive data from connections"""
    
    def is_inlet(self) -> bool:
        return True
    
    def __post_init__(self):
        super().__post_init__()
        
        # Create data field if needed
        if self.data is None:
            self.data = DataFieldFactory.create(
                type_cls=self.type_cls,
                is_pooled=self.is_pooled,
                is_array=getattr(self, 'is_array', False),
                element_type_cls=self.element_type_cls
            )


@dataclass
class PortOutlet(DataPort):
    """Outlet port - can send data to connections"""
    
    def __post_init__(self):
        super().__post_init__()
        
        # Create data field if needed
        if self.data is None:
            # Outlets cannot be pooled
            self.data = DataFieldFactory.create(
                type_cls=self.type_cls,
                is_pooled=False,
                is_array=getattr(self, 'is_array', False),
                element_type_cls=self.element_type_cls
            )