"""
Haywire Node Data Structure
===========================
An elegant, performant data structure for the Haywire node system with automatic
property-inlet binding and UI-agnostic design.
"""

from typing import Any, Dict, Optional, Callable, Set, Union, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum
from collections import defaultdict


# Data type definitions
class DataType(Enum):
    INT = 'int'
    FLOAT = 'float'
    STR = 'str'
    BOOL = 'bool'
    BYTES = 'bytes'
    DICT = 'dict'
    OBJECT = 'object'


class DataCategory(Enum):
    SCALAR = 'scalar'
    LIST = 'list'
    SET = 'set'
    DICT = 'dict'


class FlowType(Enum):
    CTRL = 'control'
    DATA = 'data'
    CALLBACK = 'callback'
    NONE = 'none'


class CouplingType(Enum):
    ONE = 'one'
    MANY = 'many'
    NONE = 'none'


@dataclass
class DataField(ABC):
    """Abstract base class for data fields with change notification"""
    type: DataType
    category: DataCategory
    is_dirty: bool = True
    is_multi: bool = False
    _observers: Set[Callable] = field(default_factory=set, init=False, repr=False)
    
    @abstractmethod
    def set_value(self, value: Any, source_id: str = None):
        """Set value with optional source tracking"""
        pass
    
    @abstractmethod
    def get_value(self):
        """Get the current value"""
        pass
    
    @abstractmethod
    def remove_source(self, source_id: str):
        """Remove a source connection"""
        pass
    
    @abstractmethod
    def has_sources(self) -> bool:
        """Check if field has any active sources"""
        pass
    
    @abstractmethod
    def get_values_list(self) -> list[Any]:
        """Get values as list"""
        pass
    
    @abstractmethod
    def get_source_ids(self) -> list[str]:
        """Get all source IDs (empty for scalar fields)"""
        pass
    
    def add_observer(self, callback: Callable):
        """Add a callback for value changes"""
        self._observers.add(callback)
    
    def remove_observer(self, callback: Callable):
        """Remove a callback for value changes"""
        self._observers.discard(callback)
    
    def _notify_observers(self):
        """Notify all observers of value change"""
        for callback in self._observers:
            try:
                callback(self.get_value())
            except Exception as e:
                # Log error but don't break the chain
                print(f"Observer callback error: {e}")
    
    def mark_clean(self):
        """Mark field as clean after processing"""
        self.is_dirty = False
    
    def to_dict(self) -> dict:
        """Convert to dict for serialization"""
        return {
            'type': self.type.value if hasattr(self.type, 'value') else self.type,
            'category': self.category.value if hasattr(self.category, 'value') else self.category,
            'value': self.get_value(),
            'is_dirty': self.is_dirty
        }


@dataclass
class SingleField(DataField):
    """Single-value data field"""
    value: Any = None
    default_value: Any = None
    
    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """Set single value (source_id is ignored for scalar fields)"""
        if self.value != value:
            self.value = value
            self.is_dirty = True
            if source_id is None:
                # if the value is set via UI, it is the default value   
                self.default_value = value
            self._notify_observers()
    
    def get_value(self):
        """Get the current value"""
        return self.value
    
    def remove_source(self, source_id: str):
        """Remove source - for scalar fields, set back to default value"""
        self.value = self.default_value
        self.is_dirty = True    
        self._notify_observers()
    
    def has_sources(self) -> bool:
        """Check if field has a value"""
        return self.value is not None
    
    def get_values_list(self) -> list[Any]:
        """Get values as list"""
        return [self.value] if self.value is not None else []
    
    def get_source_ids(self) -> list[str]:
        """Get all source IDs (empty for scalar fields)"""
        return []
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization"""
        result = super().to_dict()
        result['is_multi'] = False
        return result


@dataclass
class MultiField(DataField):
    """Multi-value data field for many-to-one connections"""
    value: dict = field(default_factory=dict)  # {source_id: value}
    is_multi: bool = True
    _aggregated_value: Any = field(default=None, init=False, repr=False)
    
    def set_value(self, value: Any, source_id: str = None):
        """Set value from a specific source"""
        if source_id is None:
            raise ValueError("source_id required for MultiField")
        if self.value.get(source_id) != value:
            self.value[source_id] = value
            self._aggregated_value = None  # Invalidate cache
            self.is_dirty = True
            self._notify_observers()
    
    def get_value(self):
        """Get aggregated value as dict"""
        if self._aggregated_value is None:
            self._aggregated_value = dict(self.value)
        return self._aggregated_value
    
    def remove_source(self, source_id: str):
        """Remove a specific source"""
        if source_id in self.value:
            del self.value[source_id]
            self._aggregated_value = None
            self.is_dirty = True
            self._notify_observers()
    
    def has_sources(self) -> bool:
        """Check if field has any sources"""
        return len(self.value) > 0
    
    def get_values_list(self) -> List[Any]:
        """Get values as list"""
        return list(self.value.values())
    
    def has_source(self, source_id: str) -> bool:
        """Check if a specific source exists"""
        return source_id in self.value
    
    def get_source_ids(self) -> List[str]:
        """Get all source IDs"""
        return list(self.value.keys())
    
    def clear_sources(self):
        """Clear all sources"""
        if self.value:
            self.value.clear()
            self._aggregated_value = None
            self.is_dirty = True
            self._notify_observers()
    
    def to_dict(self) -> dict:
        """Convert to dict for serialization"""
        result = super().to_dict()
        result['is_multi'] = True
        return result

@dataclass
class DataFieldSpec:
    """Factory specification for creating DataField instances"""
    type: DataType
    category: DataCategory = DataCategory.SCALAR
    value: Any = None
    
    def create_field(self, coupling_type: CouplingType | None = None) -> DataField:
        """Create appropriate DataField instance based on coupling type"""
        if coupling_type == CouplingType.MANY:
            # Create MultiField
            return MultiField(
                type=self.type,
                category=self.category,
                value={},
                is_multi=True
            )
        else:
            # Create SingleField (for ONE or NONE coupling)
            return SingleField(
                type=self.type,
                category=self.category,
                value=self.value,
                is_multi=False
            )


class ConfigurableElement:
    """Base class for configs, properties, inlets, outlets"""
    def __init__(self, element_id: str, name: str, description: str = "",
                 **kwargs):
        self.id = element_id
        self.name = name
        self.description = description
        self.is_visible = kwargs.get('is_visible', True)
        self.is_enabled = kwargs.get('is_enabled', True)
        self.ui = kwargs.get('ui', {})
        self.metadata = kwargs  # Store any additional UI hints
    
    def to_dict(self):
        """Convert to dict for serialization"""
        result = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_visible': self.is_visible,
            'is_enabled': self.is_enabled,
            'ui': self.ui,
            **self.metadata
        }
        return result


class Config(ConfigurableElement):
    """Configuration element for node behavior"""
    def __init__(self, element_id: str, name: str, data: DataFieldSpec, 
                description: str = "", callback: Optional[Callable] = None, **kwargs):
        super().__init__(element_id, name, description=description, data=data, **kwargs)
        self.callback = callback
        self.is_locked = kwargs.get('is_locked', False)

        # Handle data field creation
        if data:
            self.data = data.create_field()
        else:
            self.data = None
        
        # Auto-trigger callback on value change
        if callback:
            data.add_observer(lambda v: callback())

    def to_dict(self):
        """Convert to dict for serialization"""
        result = super().to_dict()
        result.update({
            'flow_type': self.flow_type.value,
            'is_connected': self.is_connected,
            'data': self.data.to_dict()
        })
        return result


class Inlet(ConfigurableElement):
    """Data inlet for receiving values"""
    def __init__(self, element_id: str, name: str, flow_type: FlowType, 
                data: DataFieldSpec | None = None, description: str = "", 
                coupling_type: CouplingType | None = None, mode: str = 'optional', **kwargs):
        # Now call parent constructor
        super().__init__(element_id, name, description=description, data=data, **kwargs)

        if coupling_type is None:
            # Default to ONE coupling type when not specified
            self.coupling_type = CouplingType.ONE
        else:
            self.coupling_type = coupling_type

        # Handle data field creation
        if data:
            self.data = data.create_field(self.coupling_type)
        else:
            self.data = None
        
        self.flow_type = flow_type
        self.mode = mode
        self.is_connected = False
        self.is_lazy = kwargs.get('is_lazy', False)
                            
    def set_value_from_source(self, source_id: str, value: Any):
        """Convenience method for setting value from a specific source"""
        if self.data:
            self.data.set_value(value, source_id=source_id)
        # Naturally, if a value is set, the inlet is connected
        self.is_connected = True
    
    def remove_source(self, source_id: str):
        """Remove a specific source connection"""
        if self.data and self.coupling_type == CouplingType.MANY:
            self.data.remove_source(source_id)
    
    def to_dict(self):
        """Convert to dict for serialization"""
        result = super().to_dict()
        result.update({
            'flow_type': self.flow_type.value,
            'coupling_type': self.coupling_type.value,
            'mode': self.mode,
            'is_connected': self.is_connected,
            'is_lazy': self.is_lazy,
            'data': self.data.to_dict() if self.data else None
        })
        return result


class Outlet(ConfigurableElement):
    """Data outlet for sending values"""
    def __init__(self, element_id: str, name: str, flow_type: FlowType, 
                 data: DataFieldSpec, description: str = "", **kwargs):
        super().__init__(element_id, name, description=description, data=data, **kwargs)

        self.data = data.create_field()
        self.flow_type = flow_type
        self.is_connected = False
        self.pipes = []  # List of pipes to connected inlets
    
    def to_dict(self):
        """Convert to dict for serialization"""
        result = super().to_dict()
        result.update({
            'flow_type': self.flow_type.value,
            'is_connected': self.is_connected,
            'data': self.data.to_dict()
        })
        return result


class NodeData:
    """Main data structure for a Haywire node"""
    def __init__(self):
        self.configs: Dict[str, Config] = {}
        self.inlets: Dict[str, Inlet] = {}
        self.outlets: Dict[str, Outlet] = {}
        
        # Performance optimization: direct access caches
        self._inlet_data_cache = {}
        self._cache_dirty = True
    
    def add_config(self, config: Config):
        """Add a configuration element"""
        self.configs[config.id] = config
        return config
    
    def add_inlet(self, inlet: Inlet):
        """Add an inlet element"""
        self.inlets[inlet.id] = inlet
        self._cache_dirty = True        
        return inlet
    
    def add_outlet(self, outlet: Outlet):
        """Add an outlet element"""
        self.outlets[outlet.id] = outlet
        return outlet
    
    def get_inlet_value(self, inlet_id: str) -> Any:
        """Fast access to inlet value (cached)"""
        if self._cache_dirty:
            self._rebuild_cache()
        
        if inlet_id in self._inlet_data_cache:
            data = self._inlet_data_cache[inlet_id]
            value = data.get_value()
            
            # For multi-value inlets, provide options to get data
            if data.is_multi:
                # Return the dict by default, but could be configured
                return value  # Dict of {source_id: value}
            return value
        return None
    
    def get_inlet_values_list(self, inlet_id: str) -> List[Any]:
        """Get inlet values as list (useful for many-coupling inlets)"""
        if self._cache_dirty:
            self._rebuild_cache()
        
        if inlet_id in self._inlet_data_cache:
            data = self._inlet_data_cache[inlet_id]
            return data.get_values_list()
        return []
    
    def set_outlet_value(self, outlet_id: str, value: Any):
        """Set outlet value and propagate through pipes"""
        if outlet_id in self.outlets:
            outlet = self.outlets[outlet_id]
            outlet.data.set_value(value)
            
            # Propagate to connected inlets through pipes
            for pipe in outlet.pipes:
                pipe.propagate(value)
    
    def _rebuild_cache(self):
        """Rebuild inlet data cache for performance"""
        self._inlet_data_cache = {
            inlet_id: inlet.data 
            for inlet_id, inlet in self.inlets.items() 
            if inlet.data
        }
        self._cache_dirty = False
    
    def get_dirty_inlets(self) -> List[str]:
        """Get list of dirty inlet IDs"""
        return [
            inlet_id for inlet_id, inlet in self.inlets.items()
            if inlet.data and inlet.data.is_dirty
        ]
    
    def mark_inlets_clean(self):
        """Mark all inlets as clean after processing"""
        for inlet in self.inlets.values():
            if inlet.data:
                inlet.data.mark_clean()
    
    def to_dict(self) -> Dict:
        """Serialize to dict structure"""
        return {
            'configs': {k: v.to_dict() for k, v in self.configs.items()},
            'inlets': {k: v.to_dict() for k, v in self.inlets.items()},
            'outlets': {k: v.to_dict() for k, v in self.outlets.items()}
        }


# Example usage showing the elegant API with inheritance
class ExampleNode(NodeData):
    def __init__(self):
        super().__init__()
        self._setup_node()
    
    def _setup_node(self):
        # Add config with callback
        self.add_config(Config(
            'precision',
            'Precision',
            DataFieldSpec(DataType.INT, value=2),
            callback=self.on_precision_changed,
            ui={
                'widget': 'slider',
                'properties': {
                    'min': 0,
                    'max': 10
                }
            }
        ))
        
        # Add inlet with default value (single coupling)
        self.add_inlet(Inlet(
            'value_in',
            'Input Value',
            FlowType.DATA,
            data=DataFieldSpec(DataType.FLOAT, value=1.0),
            ui={
                'widget': 'number',
                'properties': {
                    'min': 0.1,
                    'max': 10.0
                }
            }
        ))
        
        # Add inlet for multi-value input (many coupling)
        self.add_inlet(Inlet(
            'multi_values',
            'Multiple Values',
            FlowType.DATA,
            data=DataFieldSpec(DataType.FLOAT, value=dict())
        ))
        
        # Add outlet
        self.add_outlet(Outlet(
            'result_out',
            'Result',
            FlowType.DATA,
            DataFieldSpec(DataType.FLOAT)
        ))
    
    def on_precision_changed(self):
        """Handle precision config change"""
        print(f"Precision changed to: {self.configs['precision'].data.get_value()}")
    
    def worker(self, context: dict):
        """Worker function with elegant data access"""
        # Direct access without .data prefix
        input_value = self.get_inlet_value('value_in')
        
        # Get multi-inlet values
        multi_values_dict = self.get_inlet_value('multi_values')  # Dict
        multi_values_list = self.get_inlet_values_list('multi_values')  # List
        
        # Get config - direct access
        precision = self.configs['precision'].data.get_value()
        
        # Process
        result = round(input_value * 2, precision)
        
        # If we have multiple inputs, sum them
        if multi_values_list:
            sum_multi = sum(multi_values_list)
            result += sum_multi
        
        # Set output
        self.set_outlet_value('result_out', result)
        
        # Mark inlets as clean
        self.mark_inlets_clean()
        
        return {'next_pin': 'ctrl_out'}


# Alternative: If you need HaywireNode base class functionality
class HaywireNode(NodeData):
    """Base class combining HaywireNode requirements with NodeData"""
    def __init__(self, node_id: str, graph):
        super().__init__()
        self.node_id = node_id
        self.graph = graph
        
        # Node metadata (from your specification)
        self.node_name = None
        self.node_display_name = None
        self.node_package = None
        self.node_library_name = None
        self.node_library_url = None
        self.node_search_tags = []
        self.node_menu = None
        self.node_version = None
        
        # Runtime attributes
        self.help_md = None
        self.help_url = 'https://haywire.io/docs/node-help'
        self.is_control_node = False
        self.is_data_node = True
        self.is_loopback_node = False
        self.can_be_muted = True
        self.is_muted = False
        self.ui_default_color = '#FFFFFF'
        self.ui_custom_color = '#000000'
        self.ui_posX = 0
        self.ui_posY = 0
        self.ui_width = 100
        self.ui_height = 100
        
    @abstractmethod
    def worker(self, context: dict):
        """Override in subclasses"""
        pass


# Example showing how pipes would work with multi-value inlets
class Pipe:
    """Example pipe class for data propagation"""
    def __init__(self, source_outlet: Outlet, target_inlet: Inlet, pipe_id: str):
        self.source_outlet = source_outlet
        self.target_inlet = target_inlet
        self.pipe_id = pipe_id
        
        # Add this pipe to outlet's pipe list
        source_outlet.pipes.append(self)
    
    def propagate(self, value: Any):
        """Propagate value through pipe using polymorphic DataField interface"""
        # The DataField subclass will handle the logic based on its type
        # ScalarField ignores source_id, MultiField uses it
        self.target_inlet.set_value_from_source(self.pipe_id, value)    


    def disconnect(self):
        """Disconnect the pipe using polymorphic DataField interface"""
        # Remove from outlet's pipes
        self.source_outlet.pipes.remove(self)
        
        # Remove source using polymorphic interface
        # ScalarField will clear its value, MultiField will remove the specific source
        self.target_inlet.remove_source(self.pipe_id)
        
        # Update connection status based on remaining sources
        # Use polymorphic has_sources method
        self.target_inlet.is_connected = self.target_inlet.data.has_sources() if self.target_inlet.data else False
