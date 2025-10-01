from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..data.specs import DataFieldSpec
from ..data.fields import DataField
from ..data.enums import FlowType

@dataclass
class ConfigurableElement:
    """Base for configs, properties, inlets, outlets
    
    Intentionally broad to unify access patterns.
    Not all fields used by all subclasses.
    """
    id: str
    init: Optional[DataFieldSpec] = None
    label: str = ''
    flow_type: FlowType = FlowType.NONE
    widget: Optional[str] = None
    ui: dict = field(default_factory=dict)
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
        if isinstance(self.flow_type, FlowType):
            self.flow_type = self.flow_type.value
        
        # Copy from init if available
        if self.init:
            if self.label == '' and self.init.label:
                self.label = self.init.label
            if self.widget is None:
                self.widget = self.init.widget
            if not self.ui:
                self.ui = self.init.ui
    
    def is_pin(self) -> bool:
        return self.flow_type != FlowType.NONE.value
    
    def is_inlet(self) -> bool:
        return False
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'label': self.label,
            'widget': self.widget,
            'ui': self.ui,
            **self.metadata
        }

@dataclass
class Inlet(ConfigurableElement):
    def is_inlet(self) -> bool:
        return True
    
    def __post_init__(self):
        super().__post_init__()
        # Auto-trigger callback on value change
        if self.callback and self.data:
            self.data.add_observer(lambda v: self.callback() if self.callback else None)
        
        # Create data field if needed
        if self.data is None and self.flow_type == FlowType.DATA.value:
            if self.init:
                self.data = self.init.create_field(is_pooled=self.is_pooled)

@dataclass
class Outlet(ConfigurableElement):
    def __post_init__(self):
        super().__post_init__()
        # Create data field if needed
        if self.data is None and self.flow_type == FlowType.DATA.value:
            if self.init:
                self.data = self.init.create_field(is_pooled=False)


@dataclass
class PinSpec:
    """Specification for creating any configurable element"""
    flow_type: FlowType
    data_spec: Optional[DataFieldSpec] = None
    label: str = ''
    widget: Optional[str] = None
    ui: dict = None
    is_pooled: bool = False
    callback: Optional[Callable] = None
    is_config: bool = False
    is_property: bool = False
    is_outlet: bool = False
    
    def create_inlet(self, element_id: str, node_instance=None) -> Inlet:
        """Instantiate an Inlet from this spec"""
        element = Inlet(
            id=element_id,
            init=self.data_spec,
            label=self.label or element_id.replace('_', ' ').title(),
            flow_type=self.flow_type,
            is_pooled=self.is_pooled,
            widget=self.widget,
            ui=self.ui or {},
            callback=None,  # Set up callback below
            data=self.data_spec.create_field(self.is_pooled) if self.data_spec else None
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

    def create_outlet(self, element_id: str) -> Outlet:
        """Instantiate an Outlet from this spec"""
        return Outlet(
            id=element_id,
            init=self.data_spec,
            label=self.label or element_id.replace('_', ' ').title(),
            flow_type=self.flow_type,
            data=self.data_spec.create_field(False) if self.data_spec else None
        )
    

class PinBuilder:
    """Factory for creating PinSpecs"""

    @staticmethod
    def config(spec: DataFieldSpec, label: str = '', callback=None, **kwargs) -> PinSpec:
        """Config - has callback, no pin visible"""
        return PinSpec(
            flow_type=FlowType.NONE,
            data_spec=spec,
            label=label,
            callback=callback,
            is_config=True,
            **kwargs
        )
    
    @staticmethod
    def property(spec: DataFieldSpec, label: str = '', **kwargs) -> PinSpec:
        """Property - no callback, no pin visible"""
        return PinSpec(
            flow_type=FlowType.NONE,
            data_spec=spec,
            label=label,
            is_property=True,
            **kwargs
        )
        
    @staticmethod
    def inlet(spec: DataFieldSpec, label: str = '', **kwargs) -> PinSpec:
        return PinSpec(
            flow_type=FlowType.DATA,
            data_spec=spec,
            label=label,
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
    def outlet(spec: DataFieldSpec, label: str = '', **kwargs) -> PinSpec:
        return PinSpec(
            flow_type=FlowType.DATA,
            data_spec=spec,
            label=label,
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