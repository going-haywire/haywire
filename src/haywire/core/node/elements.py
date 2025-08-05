from __future__ import annotations
from typing import Any, Callable

from ..data.specs import DataFieldSpec
from ..data.fields import DataField
from ..data.enums import CouplingType, FlowType


class ConfigurableElement:
    """Base class for configs, properties, inlets, outlets"""
    def __init__(self, element_id: str, **kwargs):
        self.id: str = element_id
        self.init: DataFieldSpec | None = kwargs.get('init', None)
        self.label: str = kwargs.get('label', '')
        self.description: str = kwargs.get('description', '')
        self.data: DataField | None = kwargs.get('data', None)
        self.widget: str | None = kwargs.get('widget', None)
        self.ui: dict[str, Any] = kwargs.get('ui', {})
        self.metadata: dict[str, Any] = kwargs  # Store any additional UI hints

        if self.init:
            if self.label == '':
                self.label = self.init.label
            if self.description == '':
                self.description = self.init.description
            if self.widget is None:
                self.widget = self.init.widget
            if not self.ui:
                self.ui = self.init.ui
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization"""
        result = {
            'id': self.id,
            'label': self.label,
            'description': self.description,
            'widget': self.widget,
            'ui': self.ui,
            **self.metadata
        }
        return result


class Config(ConfigurableElement):
    """Configuration element for node behavior"""
    def __init__(
            self, 
            element_id: str, 
            callback: Callable[[], None] | None = None, 
            **kwargs
        ):
        super().__init__(element_id, **kwargs)

        # Handle data field creation
        if self.data is None:
            if self.init:
                self.data = self.init.create_field(is_pooled=False)
            else:
                raise ValueError(f"Config '{self.id}' requires a data field")
        
        self.callback = callback
        # Auto-trigger callback on value change
        if callback and self.data:
            self.data.add_observer(lambda v: callback())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization"""
        result = super().to_dict()
        result.update({
            'data': self.data.to_dict() if self.data else None
        })
        return result


class Inlet(ConfigurableElement):
    """Data inlet for receiving values"""
    def __init__(
            self, 
            element_id: str, 
            flow_type: str, 
            coupling_type: str = 'one', 
            use_mode: str = 'optional', 
            **kwargs
        ):
        super().__init__(element_id, **kwargs)

        # Handle data field creation
        if self.data is None and flow_type == FlowType.DATA:
            if self.init:
                self.data = self.init.create_field(is_pooled=coupling_type == CouplingType.MANY)
            else:
                raise ValueError(f"Inlet '{self.id}' requires a data field")
        
        self.flow_type = flow_type
        self.use_mode = use_mode
        self.is_connected = False
        self.is_lazy = kwargs.get('is_lazy', False)
                            
    def set_value_from_source(self, source_id: str, value: Any):
        """Convenience method for setting value from a specific source"""
        if self.data:
            self.data.set_value(value, source_id=source_id)
        self.is_connected = True
    
    def remove_source(self, source_id: str):
        """Remove a specific source connection"""
        if self.data:
            self.data.remove_source(source_id)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization"""
        result = super().to_dict()
        result.update({
            'flow_type': self.flow_type.value,
            'use_mode': self.use_mode,
            'is_connected': self.is_connected,
            'is_lazy': self.is_lazy,
            'data': self.data.to_dict() if self.data else None
        })
        return result


class Outlet(ConfigurableElement):
    """Data outlet for sending values"""
    def __init__(
            self, 
            element_id: str, 
            flow_type: FlowType, 
            **kwargs
        ):
        super().__init__(element_id, **kwargs)

        # Handle data field creation
        if self.data is None and flow_type == FlowType.DATA:
            if self.init:
                self.data = self.init.create_field(is_pooled=False)
            else:
                raise ValueError(f"Outlet '{self.id}' requires a data field")
 
        self.flow_type = flow_type
        self.pipes: list[Any] = []  # List of pipes to connected inlets
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization"""
        result = super().to_dict()
        result.update({
            'flow_type': self.flow_type.value
        })
        return result
