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
    STRING = 'str'
    BOOL = 'bool'
    BYTES = 'bytes'
    DICT = 'dict'
    LIST = 'list'
    OBJECT = 'object'


class DataCategory(Enum):
    SCALAR = 'scalar'
    TUPLE = 'tuple'
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
    id: str
    type: DataType
    category: DataCategory
    value: Any
    is_pooled: bool
    is_dirty: bool = field(default=True, init=False, repr=False)
    _default_value: Any = field(default=None, init=False, repr=False)
    _observers: Set[Callable] = field(default_factory=set, init=False, repr=False)
    
    def __post_init__(self):
        self._default_value = self.value

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

    def reset(self):
        """Reset field to default value"""
        self.value = self._default_value
        self.is_dirty = True    
    
    def to_dict(self) -> dict:
        """Convert to dict for serialization"""
        return {
            'id': self.id,
            'type': self.type.value if hasattr(self.type, 'value') else self.type,
            'category': self.category.value if hasattr(self.category, 'value') else self.category,
            'value': self._default_value,
            'is_dirty': self.is_dirty,
            'is_pooled': self.is_pooled,
        }


@dataclass
class SingleField(DataField):
    """Single-value data field"""

    def __post_init__(self):
        super().__post_init__()
        self.is_pooled = False

    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """Set single value (source_id is ignored for scalar fields)"""
        if self.value != value:
            self.value = value
            self.is_dirty = True
            if source_id is None:
                # if the value is set via UI, it is the default value   
                self._default_value = value
            self._notify_observers()
    
    def get_value(self):
        """Get the current value"""
        return self.value
    
    def remove_source(self, source_id: str):
        """Remove source - for scalar fields, set back to default value"""
        self.value = self._default_value
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
        return result


@dataclass
class PooledField(DataField):
    """Pooled-value data field for many-to-one connections"""
    _aggregated_value: Any = field(default=None, init=False, repr=False)

    def __post_init__(self):
        super().__post_init__()
        self.is_pooled = True

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
        result['is_pooled'] = True
        return result

@dataclass
class DataFieldSpec:
    """Factory specification for creating DataField instances
    
    Attributes:
        id: Unique identifier for the field specification
        label: Human-readable label displayed in UI
        description: Detailed description of the field's purpose
        widget: UI widget type (e.g., 'slider', 'input', 'select')
        type: Data type (INT, FLOAT, STRING, etc.)
        category: Data category (SCALAR, LIST, SET, DICT)
        value: Default value for the field
        is_pooled: Whether field accepts multiple input sources
    """
    type: DataType = DataType.STRING
    category: DataCategory = DataCategory.SCALAR
    id: str | None = field(default=None, init=False, repr=False)
    label: str | None = field(default=None, init=False, repr=False)
    description: str | None = field(default=None, init=False, repr=False)   
    widget: str | None = field(default=None, init=False, repr=False)
    ui: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    value: Any = None
    is_pooled: bool = False

    def __post_init__(self):
        if self.id is None:
            self.id = self.type.value.upper() + '_' + self.category.value.upper()
        if self.label is None:
            self.label = self.type.value.capitalize() + ':' + self.category.value.capitalize()
        if self.description is None:
            self.description = ""
        if self.value is None:
            if self.is_pooled is False: 
                if self.category == DataCategory.SCALAR:
                    if self.type == DataType.FLOAT:
                        self.value = 0.0
                    elif self.type == DataType.INT:
                        self.value = 0
                    elif self.type == DataType.BOOL:
                        self.value = False
                    elif self.type == DataType.STRING:
                        self.value = ""
                    elif self.type == DataType.LIST:
                        self.value = []
                    elif self.type == DataType.DICT:
                        self.value = {}
            else:
                self.value = {}
            
    def create_field(self, no_pooling: bool = False) -> DataField:
        """Create appropriate DataField instance based on pooled flag"""
        if no_pooling or not self.is_pooled:
            # Create SingleField 
            return SingleField(
                id=self.id,
                type=self.type,
                category=self.category,
                value=self.value,
                is_pooled=False
            )
        else:
            # Create PooledField
            return PooledField(
                id=self.id,
                type=self.type,
                category=self.category,
                value={},
                is_pooled=True
            )


def create_data_field_factory(data_type: DataType, category: DataCategory = DataCategory.SCALAR, **default_kwargs):
    """
    Create a factory function for custom data types.
    
    Example:
        # In a custom node library
        INT = create_data_field_factory(DataType.INT, DataCategory.SCALAR)
        INT_ARRAY = create_data_field_factory(DataType.INT, DataCategory.LIST)
        
        # Register for dynamic access
        DataFieldFactory.register('INT', INT)
        DataFieldFactory.register('INT_ARRAY', INT_ARRAY)
    """
    def factory_func(**kwargs) -> DataFieldSpec:
        # Merge default_kwargs with runtime kwargs, runtime takes precedence
        merged_kwargs = {**default_kwargs, **kwargs}
        return DataFieldSpec(type =  data_type, category = category, **merged_kwargs)
    return factory_func

# Examples
INT = create_data_field_factory(DataType.INT, DataCategory.SCALAR)
INT_ARRAY = create_data_field_factory(DataType.INT, DataCategory.LIST)

int = INT()
int_array = INT_ARRAY()

#####################################################

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
            if self.ui is None:
                self.ui = self.init.ui
            if self.metadata is None:
                self.metadata = self.init.metadata
        if self.widget is None:
            self.widget = 'None'
    

    def to_dict(self):
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
            callback: Optional[Callable] = None, 
            **kwargs
        ):
        super().__init__(element_id, **kwargs)

        # Handle data field creation
        if self.data is None:
            if self.init:
                self.data = self.init.create_field(no_pooling=True)
            else:
                raise ValueError(f"Config '{self.id}' requires a data field")
        
        self.callback = callback
        # Auto-trigger callback on value change
        if callback and self.data:
            self.data.add_observer(lambda v: callback())

    def to_dict(self):
        """Convert to dict for serialization"""
        result = super().to_dict()
        result.update({
            'data': self.data.to_dict()
        })
        return result


class Inlet(ConfigurableElement):
    """Data inlet for receiving values"""
    def __init__(
            self, 
            element_id: str, 
            flow_type: FlowType, 
            use_mode: str = 'optional', 
            **kwargs
        ):
        # Now call parent constructor
        super().__init__(element_id, **kwargs)

        # Handle data field creation
        if self.data is None and flow_type == FlowType.DATA:
            if self.init:
                self.data = self.init.create_field()
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
        # Naturally, if a value is set, the inlet is connected
        self.is_connected = True
    
    def remove_source(self, source_id: str):
        """Remove a specific source connection"""
        if self.data:
            self.data.remove_source(source_id)
    
    def to_dict(self):
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
                self.data = self.init.create_field()
            else:
                raise ValueError(f"Outlet '{self.id}' requires a data field")
 
        self.flow_type = flow_type
        self.pipes = []  # List of pipes to connected inlets
    
    def to_dict(self):
        """Convert to dict for serialization"""
        result = super().to_dict()
        result.update({
            'flow_type': self.flow_type.value
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
            if data.is_pooled:
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
            element_id='precision',
            label='Precision',
            init=DataFieldSpec(DataType.INT, value=2),
            callback=self.on_precision_changed,
            widget='slider',
            ui={'properties': {'min': 0, 'max': 10}}
        ))
        
        # Add inlet with default value (single coupling)
        self.add_inlet(Inlet(
            element_id='value_in',
            label='Input Value',
            flow_type=FlowType.DATA,
            init=DataFieldSpec(DataType.FLOAT, value=1.0),
            widget='number',
            ui={'properties': {'min': 0.1, 'max': 10.0}}
        ))
        
        # Add inlet for multi-value input (many coupling)
        self.add_inlet(Inlet(
            element_id='multi_values',
            label='Multiple Values',
            flow_type=FlowType.DATA,
            init=DataFieldSpec(DataType.FLOAT),
            coupling_type=CouplingType.MANY
        ))
        
        # Add outlet
        self.add_outlet(Outlet(
            element_id='result_out',
            label='Result',
            flow_type=FlowType.DATA,
            init=DataFieldSpec(DataType.FLOAT)
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
