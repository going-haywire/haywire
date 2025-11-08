from __future__ import annotations
from copy import deepcopy
from typing import Any, Callable, Dict, List, Type, TypeVar, Optional, Union
from abc import abstractmethod
from dataclasses import dataclass, field

from haywire.core.data.enums import FlowType
from haywire.core.node.dataclasses import NodeBehavior, NodeErrorInfo, NodeUIConfig, NodeUIState, NodeUserMetadata
from haywire.core.library.base_identity import BaseIdentity
from haywire.core.library.utils import derive_library_id, reg_key

T = TypeVar('T')

from .elements import Inlet, Outlet, PinSpec
from ..library.library_identity import LibraryIdentity
from ..data.specs import DataFieldSpec

@dataclass
class NodeIdentity(BaseIdentity):
    """Core identifying attributes of a node"""
    search_tags: list[str] = field(default_factory=lambda: ['add', 'sub', 'math', 'vector'])
    menu: str = 'misc/custom'
    help_md: str | None = None
    help_url: str = 'https://haywire.io/docs/node-help',
    is_error: bool = False

# ============================================================================
#    Decorator
# ============================================================================

T = TypeVar('T')

def node(cls: Type[T] = None, /, **kwargs) -> Union[Type[T], Callable[[Type[T]], Type[T]]]:
    """
    Decorator to register a class as a Haywire node.
    
    Accepts any NodeIdentity field as a keyword argument. Common arguments include:
    
    Args:
        registry_id (str, optional): Unique identifier for the node within its library.
            Defaults to class name if not provided.
        registry_key (str, optional): Full registry key (library + node ID). 
            Auto-derived from library ID and registry_id by the decorator.
            Can be manually overridden if needed.
        label (str, optional): Human-readable display name for the node.
            Defaults to class name if not provided.
        description (str, optional): Detailed description of what the node does.
            Defaults to empty string.
        search_tags (list[str], optional): Tags for searching/filtering nodes in UI.
            Defaults to empty list.
        menu (str, optional): Menu category path (e.g., 'math/arithmetic', 'io/files').
            Defaults to 'misc/custom'.
        help_md (str, optional): Markdown help content displayed in node help panel.
            Defaults to None.
        help_url (str, optional): URL to external help documentation.
            Defaults to 'https://haywire.io/docs/node-help'.
        is_error (bool, optional): Whether this node handles error cases.
            Defaults to False.
    
    Any other keyword arguments will be passed through to the NodeIdentity constructor.
    See the NodeIdentity dataclass for the complete list of available fields.

    Usage:
        # Minimal usage - uses class name for registry_id and label
        @node
        class MyNode(BaseNode): ...

        # Common customization
        @node(label="Custom Node", description="Does custom things")
        class MyNode(BaseNode): ...

        # Full customization
        @node(
            registry_id="my_custom_node",
            label="My Custom Node", 
            description="Performs custom calculations",
            search_tags=["custom", "math", "utility"],
            menu="custom/math",
            help_md="## Custom Node\n\nThis node does...",
            is_error=False
        )
        class CustomNode(BaseNode): ...

        # Error handling node
        @node(is_error=True, label="Error Handler", menu="system/errors")
        class ErrorNode(BaseNode): ...
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseNode):
            raise TypeError(f"@node can only be applied to BaseNode subclasses, got {inner_cls}")

        # Set defaults from class name if not provided
        kwargs.setdefault('registry_id', inner_cls.__name__)
        kwargs.setdefault('label', inner_cls.__name__)
        
        # Auto-derive registry_key if not explicitly set
        if 'registry_key' not in kwargs:
            library_id = derive_library_id(inner_cls)
            kwargs['registry_key'] = reg_key(library_id, kwargs['registry_id'])
        
        inner_cls.class_identity = NodeIdentity(**kwargs)
        return inner_cls

    return decorator if cls is None else decorator(cls)


# ============================================================================
# Node Metaclass
# ============================================================================

class NodeMeta(type):
    """Metaclass that processes pin declarations"""
    
    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)
        
        # Collect PinSpecs from this class only
        pin_specs = {}
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, PinSpec):
                pin_specs[attr_name] = attr_value
        
        # Store on class for later use
        new_class._pin_specs = pin_specs
        
        return new_class

@abstractmethod
class NodeData():
    """Main data structure for a Haywire node"""
    def __init__(self):
        """Initialize all pins from class definitions"""
        self.configs = {}
        self.properties = {}
        self.inlets: Dict[str, Inlet] = {}
        self.outlets: Dict[str, Outlet] = {}
        
        # Collect pin specs from all classes in MRO
        for klass in reversed(self.__class__.__mro__):
            if not hasattr(klass, '_pin_specs'):
                continue
                
            for attr_name, pin_spec in klass._pin_specs.items():
                if pin_spec.is_outlet:
                    pin = pin_spec.create_outlet(attr_name)
                    self.outlets[attr_name] = pin
                elif pin_spec.is_config:
                    pin = pin_spec.create_inlet(attr_name)
                    self.configs[attr_name] = pin
                elif pin_spec.is_property:
                    pin = pin_spec.create_inlet(attr_name)
                    self.properties[attr_name] = pin
                elif pin_spec.flow_type in (FlowType.CTRL, FlowType.DATA, FlowType.CALLBACK):
                    pin = pin_spec.create_inlet(attr_name)
                    self.inlets[attr_name] = pin
                
                if pin:
                    setattr(self, attr_name, pin)
        
        self._cache_dirty = True
    
    # deprecated methods for dynamic pin management
    def add_inlet(self, inlet: Inlet) -> Inlet:
        """Add an inlet element"""
        if '__' in inlet.id:
            # Handle special case for inlet IDs containing '__' - reserved to split concatenated attributes
            raise ValueError("Inlet ID cannot contain double underscores '__'")
        self.inlets[inlet.id] = inlet
        self._cache_dirty = True        
        return inlet
    
    #deprecated methods for dynamic pin management
    def add_outlet(self, outlet: Outlet) -> Outlet:
        """Add an outlet element"""
        if '__' in outlet.id:
            # Handle special case for outlet IDs containing '__' - reserved to split concatenated attributes
            raise ValueError("Outlet ID cannot contain double underscores '__'")
        self.outlets[outlet.id] = outlet
        return outlet
    

    def add_inlet_experimental(self, pin_id: str, spec: DataFieldSpec = None, 
                  label: str = '', **kwargs) -> Inlet:
        """Add inlet (works for both static and dynamic)"""
        pin_spec = PinSpec(
            flow_type=FlowType.CTRL if spec is None else FlowType.DATA,
            data_spec=spec,
            label=label,
            **kwargs
        )
        inlet = pin_spec.create_inlet(pin_id)
        self.inlets[pin_id] = inlet
        setattr(self, pin_id, inlet)
        self._cache_dirty = True
        return inlet
    
    def add_outlet_experimental(self, pin_id: str, spec: DataFieldSpec = None,
                   label: str = '', **kwargs) -> Outlet:
        """Add outlet (works for both static and dynamic)"""
        pin_spec = PinSpec(
            flow_type=FlowType.CTRL if spec is None else FlowType.DATA,
            data_spec=spec,
            label=label,
            **kwargs
        )
        outlet = pin_spec.create_outlet(pin_id)
        self.outlets[pin_id] = outlet
        setattr(self, pin_id, outlet)
        return outlet
 

    def to_dict(self) -> dict:
        """Serialize node to dictionary - captures CURRENT state of all pins"""
        from dataclasses import asdict
        
        return {
            # Serialize ALL pins as they currently exist
            'configs': {k: v.to_dict() for k, v in self.configs.items()},
            'properties': {k: v.to_dict() for k, v in self.properties.items()},
            'inlets': {k: v.to_dict() for k, v in self.inlets.items()},
            'outlets': {k: v.to_dict() for k, v in self.outlets.items()}
        }
    
    def load_state(self, state_dict: dict):
        """Load serialized state - recreate the EXACT pin configuration"""
        
        # Step 1: Clear out class-generated defaults that aren't in saved state
        # Remove configs not in saved state
        if 'configs' in state_dict:
            for name in list(self.configs.keys()):
                if name not in state_dict['configs']:
                    del self.configs[name]
                    if hasattr(self, name):
                        delattr(self, name)
        
        # Remove properties not in saved state
        if 'properties' in state_dict:
            for name in list(self.properties.keys()):
                if name not in state_dict['properties']:
                    del self.properties[name]
                    if hasattr(self, name):
                        delattr(self, name)
        
        # Remove inlets not in saved state
        if 'inlets' in state_dict:
            for name in list(self.inlets.keys()):
                if name not in state_dict['inlets']:
                    del self.inlets[name]
                    if hasattr(self, name):
                        delattr(self, name)
        
        # Remove outlets not in saved state
        if 'outlets' in state_dict:
            for name in list(self.outlets.keys()):
                if name not in state_dict['outlets']:
                    del self.outlets[name]
                    if hasattr(self, name):
                        delattr(self, name)
        
        # Step 2: Load or create all pins from saved state
        # Load configs
        if 'configs' in state_dict:
            for name, config_data in state_dict['configs'].items():
                if name in self.configs:
                    # Update existing
                    self.configs[name].load_from_dict(config_data)
                else:
                    # Create new (was dynamically added)
                    config = Inlet.from_dict(config_data)
                    self.configs[name] = config
                    setattr(self, name, config)
        
        # Load properties
        if 'properties' in state_dict:
            for name, prop_data in state_dict['properties'].items():
                if name in self.properties:
                    self.properties[name].load_from_dict(prop_data)
                else:
                    prop = Inlet.from_dict(prop_data)
                    self.properties[name] = prop
                    setattr(self, name, prop)
        
        # Load inlets
        if 'inlets' in state_dict:
            for name, inlet_data in state_dict['inlets'].items():
                if name in self.inlets:
                    self.inlets[name].load_from_dict(inlet_data)
                else:
                    inlet = Inlet.from_dict(inlet_data)
                    self.inlets[name] = inlet
                    setattr(self, name, inlet)
        
        # Load outlets
        if 'outlets' in state_dict:
            for name, outlet_data in state_dict['outlets'].items():
                if name in self.outlets:
                    self.outlets[name].load_from_dict(outlet_data)
                else:
                    outlet = Outlet.from_dict(outlet_data)
                    self.outlets[name] = outlet
                    setattr(self, name, outlet)
        
        # Load other state
        if 'ui_state' in state_dict:
            self.ui_state = NodeUIState.from_dict(state_dict['ui_state'])
        if 'metadata' in state_dict:
            self.metadata = NodeUserMetadata.from_dict(state_dict['metadata'])
        
        self._cache_dirty = True        

@abstractmethod
class BaseNode(NodeData, metaclass=NodeMeta):
    """Base class combining HaywireNode requirements with NodeData"""
    
    def __init__(self, node_id: str, graph: Any):
        super().__init__()
        self.node_id = node_id
        self.graph = graph
        self.error_info: NodeErrorInfo | None = None
                    
        self.behavior = NodeBehavior()
        self.ui_config = NodeUIConfig()
        self.ui_state = NodeUIState()
        self.metadata = NodeUserMetadata()

    @property
    def identity(self) -> NodeIdentity:
        return self.__class__.class_identity

    @property
    def library(self) -> LibraryIdentity:
        return self.__class__.class_library

    @abstractmethod
    def worker(self, context: dict) -> dict | None:
        """The main execution logic of the node. Override in subclasses."""
        pass
           
    def to_dict(self) -> dict:
        """Serialize node to dictionary"""
        from dataclasses import asdict
        
        return {
            'node_id': self.node_id,
            'registry_key': self.identity.registry_key,
            'library': asdict(self.library) if self.library else None,
            'identity': asdict(self.identity),
            'behavior': asdict(self.behavior),
            'ui_config': asdict(self.ui_config),
            'ui_state': asdict(self.ui_state),
            'metadata': asdict(self.metadata),
            'inlets': {k: v.to_dict() for k, v in self.inlets.items()},
            'outlets': {k: v.to_dict() for k, v in self.outlets.items()}
        }

