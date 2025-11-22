from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from ..data.fields import DataField, PooledField, SingleField
from ..data.enums import FlowType
from .identity import DataPortIdentity
from .type_interface import IType

@dataclass
class DataPort(DataPortIdentity):
    """Extended DataPortIdentity with runtime port information.
    
    Adds runtime-specific fields on top of the identity:
    - id: Port identifier within the node (different from registry_id!)
    - flow_type: CTRL, DATA, CALLBACK, or NONE
    - data: Runtime data field for storing values
    - Connection state, pooling, callbacks, etc.
    """
    # Port identifier within node (different from registry_id!)
    # Must have default since parent class fields all have defaults
    id: str = ''
        
    # Runtime fields (not in identity)
    data: Optional[DataField] = None
    
    # Pin-specific (unused for Config/Property)
    is_connected: bool = False
    
    # Inlet-specific (unused for Outlet/Config/Property)
    is_pooled: bool = False
    use_mode: str = 'optional'
    is_lazy: bool = False
    
    # Outlet-specific (unused for Inlet/Config/Property)
    pipes: list = field(default_factory=list)
    
    @property
    def value(self) -> Any:
        """Get current value from data field, if available."""
        if self.data:
            return self.data.get_value()
        return None

    def __post_init__(self):
        # Note: We skip super().__post_init__() because DataPortIdentity's __post_init__
        # auto-generates registry_key, label, and defaults from registry_id, which is
        # unnecessary for runtime ports that already have these fields explicitly set.
        # This is a performance optimization, not a correctness requirement.
        pass
            
    def is_pin(self) -> bool:
        return self.flow_type != FlowType.NONE.value
    
    def is_inlet(self) -> bool:
        return False
    
    def to_dict(self) -> dict:
        """
        Serialize port to dict.
        
        If the port was created via Type.as_inlet()/as_outlet(), uses the stored
        creation recipe for compact serialization. Otherwise, serializes all fields.
        
        Returns:
            Dict with either:
            - Recipe format: {type: 'recipe', registry_key, method, kwargs}
            - Full format: {type: 'full', data: {...all fields...}}
        """
        # If port has a creation recipe, use that for serialization
        if hasattr(self, '_creation_recipe'):
            return {
                'type': 'recipe',
                **self._creation_recipe
            }
   
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
    """Factory for creating DataField instances"""

    @staticmethod
    def create(
        type_cls: IType,
        is_pooled: bool = False,
        default_override: Optional[Dict[str, Any]] = None
    ) -> DataField:
        """Create appropriate DataField instance"""

        if is_pooled:
            return PooledField(type_cls=type_cls)
        else:
            # Create default instance with optional override
            instance = (
                type_cls(**default_override)
                if default_override
                else type_cls.create_default()
            )
            return SingleField(type_cls=type_cls, default_value=instance)

@dataclass
class PortInlet(DataPort):
    def is_inlet(self) -> bool:
        return True
    
    def __post_init__(self):
        super().__post_init__()        
        # Create data field if needed
        if self.data is None:
            self.data = DataFieldFactory.create(type_cls=self.type_cls, is_pooled=self.is_pooled)

@dataclass
class PortOutlet(DataPort):
    def __post_init__(self):
        super().__post_init__()
        # Create data field if needed
        if self.data is None:
            self.data = DataFieldFactory.create(type_cls=self.type_cls, is_pooled=False)

