from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable

from ..data.specs import DataFieldSpec
from ..data.fields import DataField
from ..data.enums import FlowType


@dataclass
class ConfigurableElement:
    """Base class for configs, properties, inlets, outlets"""
    id: str
    init: DataFieldSpec | None = None
    label: str = ''
    description: str = ''
    is_inlet = False
    flow_type: str | FlowType = FlowType.NONE
    data: DataField | None = None
    widget: str | None = None
    ui: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        # Convert enum values to strings for serialization compatibility
        if isinstance(self.flow_type, FlowType):
            self.flow_type = self.flow_type.value

        if self.init:
            if self.label == '' and self.init.label is not None:
                self.label = self.init.label
            if self.description == '' and self.init.description is not None:
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


@dataclass
class Inlet(ConfigurableElement):
    """Data inlet for receiving values"""
    callback: Callable[[], None] | None = None
    is_pooled: bool = False
    use_mode: str = 'optional'
    is_connected: bool = False
    is_lazy: bool = False
    is_inlet = True  # Override base class
    
    def __post_init__(self):
        super().__post_init__()
        
        # Auto-trigger callback on value change
        if self.callback and self.data:
            self.data.add_observer(lambda v: self.callback() if self.callback else None)

        # Handle data field creation
        if self.data is None and self.flow_type == FlowType.DATA.value:
            if self.init:
                self.data = self.init.create_field(is_pooled=self.is_pooled)
            else:
                raise ValueError(f"Inlet '{self.id}' requires a data field")
                            
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
            'flow_type': self.flow_type,
            'is_pooled': self.is_pooled,
            'use_mode': self.use_mode,
            'is_connected': self.is_connected,
            'is_lazy': self.is_lazy,
            'data': self.data.to_dict() if self.data else None
        })
        return result


@dataclass
class Outlet(ConfigurableElement):
    """Data outlet for sending values"""
    pipes: list[Any] = field(default_factory=list)  # List of pipes to connected inlets
    
    def __post_init__(self):
        super().__post_init__()
        
        # Handle data field creation
        if self.data is None and self.flow_type == FlowType.DATA.value:
            if self.init:
                self.data = self.init.create_field(is_pooled=False)
            else:
                raise ValueError(f"Outlet '{self.id}' requires a data field")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization"""
        result = super().to_dict()
        result.update({
            'flow_type': self.flow_type
        })
        return result
