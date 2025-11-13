from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..data.identity import DataPortIdentity
from ..data.specs import DataFieldFactory
from ..data.fields import DataField
from ..data.enums import FlowType

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
    metadata: dict = field(default_factory=dict)
    
    # Pin-specific (unused for Config/Property)
    is_connected: bool = False
    
    # Inlet-specific (unused for Outlet/Config/Property)
    is_pooled: bool = False
    callback: Optional[Callable] = None
    use_mode: str = 'optional'
    is_lazy: bool = False
    
    # Outlet-specific (unused for Inlet/Config/Property)
    pipes: list = field(default_factory=list)
    
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

@dataclass
class PortInlet(DataPort):
    def is_inlet(self) -> bool:
        return True
    
    def __post_init__(self):
        super().__post_init__()        
        # Create data field if needed
        if self.data is None and self.flow_type == FlowType.DATA:
            self.data = DataFieldFactory.create(self, is_pooled=self.is_pooled)

        # Auto-trigger callback on value change
        if self.callback and self.data:
            self.data.add_observer(lambda v: self.callback() if self.callback else None)

@dataclass
class PortOutlet(DataPort):
    def __post_init__(self):
        super().__post_init__()
        # Create data field if needed
        if self.data is None and self.flow_type == FlowType.DATA:
            self.data = DataFieldFactory.create(self, is_pooled=False)


@DeprecationWarning
@dataclass
class PinSpec:
    """Specification for creating any configurable element"""
    flow_type: FlowType
    data_spec: Optional[DataPortIdentity] = None
    label: str = ''
    widget: Optional[str] = None
    ui: dict = None
    is_pooled: bool = False
    callback: Optional[Callable] = None
    is_config: bool = False
    is_property: bool = False
    is_outlet: bool = False
    
    def create_inlet(self, element_id: str, node_instance=None) -> PortInlet:
        """Instantiate an Inlet from this spec"""
        element = PortInlet(
            id=element_id,
            spec=self.data_spec,
            label=self.label or element_id.replace('_', ' ').title(),
            flow_type=self.flow_type,
            is_pooled=self.is_pooled,
            widget=self.widget,
            ui=self.ui or {},
            callback=None,  # Set up callback below
            data=DataFieldFactory.create(self.data_spec,is_pooled=self.is_pooled) if self.data_spec else None
        )
        
        # Set up callback for configs
        if self.callback and node_instance:
            # Bind callback to node instance
            bound_callback = lambda: self.callback(node_instance)
            element.callback = bound_callback
            
            # Attach observer to data field
            if element.data:
                element.data.add_observer(lambda v: bound_callback())
        
        return element

    def create_outlet(self, element_id: str) -> PortOutlet:
        """Instantiate an Outlet from this spec"""
        return PortOutlet(
            id=element_id,
            spec=self.data_spec,
            label=self.label or element_id.replace('_', ' ').title(),
            flow_type=self.flow_type,
            data=DataFieldFactory.create(self.data_spec,is_pooled=False) if self.data_spec else None
        )
    
@DeprecationWarning
class PortBuilder:
    """Factory for creating PinSpecs"""

    @staticmethod
    def config(spec: DataPortIdentity, label: str = '', callback=None, **kwargs) -> PinSpec:
        """
        Config - has callback, no pin visible
        
        Usage:
            PinBuilder.config(FLOAT, label='Value', callback=on_change)
            PinBuilder.config(FLOAT(label='Value'), callback=on_change)
        """
        # If label provided as kwarg, override spec
        if label:
            spec = spec(label=label)
        
        return PinSpec(
            flow_type=FlowType.NONE,
            data_spec=spec,
            label=spec.label,
            callback=callback,
            is_config=True,
            **kwargs
        )
    
    @staticmethod
    def property(spec: DataPortIdentity, label: str = '', **kwargs) -> PinSpec:
        """
        Property - no callback, no pin visible
        
        Usage:
            PinBuilder.property(FLOAT, label='Value')
            PinBuilder.property(FLOAT(label='Value'))
        """
        # If label provided as kwarg, override spec
        if label:
            spec = spec(label=label)
        
        return PinSpec(
            flow_type=FlowType.NONE,
            data_spec=spec,
            label=spec.label,
            is_property=True,
            **kwargs
        )
        
    @staticmethod
    def inlet(spec: DataPortIdentity, label: str = '', **kwargs) -> PinSpec:
        """
        Data inlet pin
        
        Usage:
            PinBuilder.inlet(FLOAT, label='Radius')
            PinBuilder.inlet(FLOAT(label='Radius', value=10.0))
        """
        # If label provided as kwarg, override spec
        if label:
            spec = spec(label=label)
        
        return PinSpec(
            flow_type=FlowType.DATA,
            data_spec=spec,
            label=spec.label,
            **kwargs
        )
    
    @staticmethod
    def ctrl_inlet(label: str = '', **kwargs) -> PinSpec:
        return PinSpec(
            flow_type=FlowType.CTRL,
            label=label,
            **kwargs
        )
    
    @staticmethod
    def callback_inlet(label: str = '', **kwargs) -> PinSpec:
        return PinSpec(
            flow_type=FlowType.CALLBACK,
            label=label,
            **kwargs
        )
    
    @staticmethod
    def outlet(spec: DataPortIdentity, label: str = '', **kwargs) -> PinSpec:
        """
        Data outlet pin
        
        Usage:
            PinBuilder.outlet(FLOAT, label='Result')
            PinBuilder.outlet(FLOAT(label='Result'))
        """
        # If label provided as kwarg, override spec
        if label:
            spec = spec(label=label)
        
        return PinSpec(
            flow_type=FlowType.DATA,
            data_spec=spec,
            label=spec.label,
            is_outlet=True,
            **kwargs
        )
    
    @staticmethod
    def ctrl_outlet(label: str = '', **kwargs) -> PinSpec:
        return PinSpec(
            flow_type=FlowType.CTRL,
            label=label,
            is_outlet=True,
            **kwargs
        )