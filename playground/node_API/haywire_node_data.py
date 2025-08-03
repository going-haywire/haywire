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
    OBJECT = 'object'


class DataCategory(Enum):
    SCALAR = 'scalar'
    LIST = 'list'
    TUPLE = 'tuple'
    SET = 'set'
    DICT = 'dict'


class FlowType(Enum):
    CTRL = 'control'
    DATA = 'data'
    CALLBACK = 'callback'
    NONE = 'none'


@dataclass
class DataField:
    """Core data structure for values with change notification"""
    type: DataType
    category: DataCategory
    value: Any = None
    is_dirty: bool = False
    is_multi: bool = False
    _observers: Set[Callable] = field(default_factory=set, init=False, repr=False)
    _aggregated_value: Any = field(default=None, init=False, repr=False)
    
    def __post_init__(self):
        """Initialize value structure based on is_multi flag"""
        if self.is_multi:
            if not isinstance(self.value, dict):
                self.value = {}  # {source_id: value}
            self._aggregated_value = None
    
    def set_value(self, value: Any, source_id: str = None):
        """Set value with optional source tracking for multi-value fields"""
        if self.is_multi:
            if source_id is None:
                raise ValueError("source_id required for multi-value DataField")
            if self.value.get(source_id) != value:
                self.value[source_id] = value
                self._aggregated_value = None  # Invalidate cache
                self.is_dirty = True
                self._notify_observers()
        else:
            # Original single-value behavior
            if self.value != value:
                self.value = value
                self.is_dirty = True
                self._notify_observers()
    
    def get_value(self):
        """Get value - returns dict for multi-value, single value otherwise"""
        if self.is_multi:
            if self._aggregated_value is None:
                # Return as dict with source IDs as keys
                self._aggregated_value = dict(self.value)
            return self._aggregated_value
        return self.value
    
    def get_values_list(self):
        """Get values as list (for multi-value fields)"""
        if self.is_multi:
            return list(self.value.values())
        return [self.value] if self.value is not None else []
    
    def remove_source(self, source_id: str):
        """Remove a source (for multi-value fields when disconnected)"""
        if self.is_multi and source_id in self.value:
            del self.value[source_id]
            self._aggregated_value = None
            self.is_dirty = True
            self._notify_observers()
    
    def clear_sources(self):
        """Clear all sources (for multi-value fields)"""
        if self.is_multi and self.value:
            self.value.clear()
            self._aggregated_value = None
            self.is_dirty = True
            self._notify_observers()
    
    def has_source(self, source_id: str) -> bool:
        """Check if a source exists (for multi-value fields)"""
        return self.is_multi and source_id in self.value
    
    def get_source_ids(self) -> List[str]:
        """Get all source IDs (for multi-value fields)"""
        if self.is_multi:
            return list(self.value.keys())
        return []
    
    def add_observer(self, callback: Callable):
        """Add a callback for value changes"""
        self._observers.add(callback)
    
    def remove_observer(self, callback: Callable):
        """Remove a value change callback"""
        self._observers.discard(callback)
    
    def _notify_observers(self):
        """Notify all observers of value change"""
        # For multi-value, pass the aggregated value
        notification_value = self.get_value()
        for observer in self._observers:
            observer(notification_value)
    
    def mark_clean(self):
        """Mark as clean after processing"""
        self.is_dirty = False
    
    def to_dict(self):
        """Convert to dict for serialization"""
        return {
            'type': self.type.value,
            'category': self.category.value,
            'value': self.value,
            'is_dirty': self.is_dirty,
            'is_multi': self.is_multi
        }


class ConfigurableElement:
    """Base class for configs, properties, inlets, outlets"""
    def __init__(self, element_id: str, name: str, description: str = "",
                 data: Optional[DataField] = None, **kwargs):
        self.id = element_id
        self.name = name
        self.description = description
        self.data = data
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
        if self.data:
            result['data'] = self.data.to_dict()
        return result


class Config(ConfigurableElement):
    """Configuration element for node behavior"""
    def __init__(self, element_id: str, name: str, data: DataField, 
                 callback: Optional[Callable] = None, **kwargs):
        super().__init__(element_id, name, data=data, **kwargs)
        self.callback = callback
        self.is_locked = kwargs.get('is_locked', False)
        
        # Auto-trigger callback on value change
        if callback:
            data.add_observer(lambda v: callback())



class Inlet(ConfigurableElement):
    """Data inlet for receiving values"""
    def __init__(self, element_id: str, name: str, flow_type: FlowType,
                 coupling_type: str = 'one', mode: str = 'optional', **kwargs):
        # Set coupling type first, before calling parent constructor
        self.flow_type = flow_type
        self.coupling_type = coupling_type
        self.mode = mode
        
        # Extract data if provided, and prepare it for multi-value if needed
        if 'data' in kwargs and coupling_type == 'many':
            data_field = kwargs['data']
            if data_field:
                data_field.is_multi = True
                if not isinstance(data_field.value, dict):
                    data_field.value = {}
        
        # Now call parent constructor
        super().__init__(element_id, name, **kwargs)
        
        self.is_connected = False
        self.is_lazy = kwargs.get('is_lazy', False)
    
    def set_value_from_source(self, source_id: str, value: Any):
        """Convenience method for setting value from a specific source"""
        if self.data:
            self.data.set_value(value, source_id=source_id)
    
    def remove_source(self, source_id: str):
        """Remove a specific source connection"""
        if self.data and self.coupling_type == 'many':
            self.data.remove_source(source_id)
    
    def to_dict(self):
        """Convert to dict for serialization"""
        result = super().to_dict()
        result.update({
            'flow_type': self.flow_type.value,
            'coupling_type': self.coupling_type,
            'mode': self.mode,
            'is_connected': self.is_connected,
            'is_lazy': self.is_lazy
        })
        return result


class Outlet(ConfigurableElement):
    """Data outlet for sending values"""
    def __init__(self, element_id: str, name: str, flow_type: FlowType,
                 data: DataField, **kwargs):
        super().__init__(element_id, name, data=data, **kwargs)
        self.flow_type = flow_type
        self.is_connected = False
        self.pipes = []  # List of pipes to connected inlets
    
    def to_dict(self):
        """Convert to dict for serialization"""
        result = super().to_dict()
        result.update({
            'flow_type': self.flow_type.value,
            'is_connected': self.is_connected
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
        
        # Initialize data field if needed
        if inlet.coupling_type == 'many' and inlet.data is None:
            # Create multi-value data field
            inlet.data = DataField(
                inlet.metadata.get('data_type', DataType.OBJECT),
                inlet.metadata.get('data_category', DataCategory.SCALAR),
                is_multi=True
            )
        
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
            DataField(DataType.INT, DataCategory.SCALAR, 2),
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
            data=DataField(DataType.FLOAT, DataCategory.SCALAR, 1.0),  # Default value
            ui={
                'widget': 'number',
                'properties': {
                    'min': 0.1,
                    'max': 10.0
                }
            }
        ))
        
        # Add inlet with many coupling
        self.add_inlet(Inlet(
            'data_in_many',
            'Multiple Inputs',
            FlowType.DATA,
            coupling_type='many',
            mode='optional',
            data=DataField(DataType.FLOAT, DataCategory.SCALAR)
        ))
        
        # Add control inlet
        self.add_inlet(Inlet(
            'ctrl_in',
            'Execute',
            FlowType.CTRL,
            coupling_type='many'
        ))
        
        # Add outlet
        self.add_outlet(Outlet(
            'result_out',
            'Result',
            FlowType.DATA,
            DataField(DataType.FLOAT, DataCategory.SCALAR)
        ))
    
    def on_precision_changed(self):
        """Handle precision config change"""
        print(f"Precision changed to: {self.configs['precision'].data.get_value()}")
    
    def worker(self, context: dict):
        """Worker function with elegant data access"""
        # Direct access without .data prefix
        input_value = self.get_inlet_value('value_in')
        
        # Get multi-inlet values
        multi_values_dict = self.get_inlet_value('data_in_many')  # Dict
        multi_values_list = self.get_inlet_values_list('data_in_many')  # List
        
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
        """Propagate value through pipe"""
        if self.target_inlet.coupling_type == 'many':
            # Use pipe ID as source identifier
            self.target_inlet.data.set_value(value, source_id=self.pipe_id)
        else:
            # Single coupling - direct set
            self.target_inlet.data.set_value(value)
    
    def disconnect(self):
        """Disconnect the pipe"""
        # Remove from outlet's pipes
        self.source_outlet.pipes.remove(self)
        
        # Update inlet connection status
        if self.target_inlet.coupling_type == 'many':
            # Multi-value inlet - remove this specific source
            self.target_inlet.data.remove_source(self.pipe_id)
            # Update connection status based on remaining sources
            remaining_sources = self.target_inlet.data.get_source_ids() if self.target_inlet.data else []
            self.target_inlet.is_connected = len(remaining_sources) > 0
        else:
            # Single coupling - mark as disconnected
            self.target_inlet.is_connected = False
