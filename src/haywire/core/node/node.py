from __future__ import annotations
import inspect
from typing import Any, Dict, List
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from haywire.core.data.enums import FlowType

from .elements import Inlet, Outlet, PinSpec
from ..inventory.base import LibraryMetadata


# ============================================================================
# Custom Exceptions
# ============================================================================

class NodeDiscoveryError(Exception):
    """Base exception for node discovery issues"""
    pass


class NodeNotFoundError(NodeDiscoveryError):
    """Node with specified criteria not found"""
    pass


class NodeAmbiguousError(NodeDiscoveryError):
    """Multiple nodes found, cannot determine which to use"""
    pass


class NodeVersionError(NodeDiscoveryError):
    """Node version compatibility issue"""
    pass


class NodeValidationError(NodeDiscoveryError):
    """Node class is missing required attributes"""
    pass


def is_node(cls):
    """Check if a class is a valid Haywire node class."""
    try:
        return (inspect.isclass(cls) and
                issubclass(cls, BaseNode) and
                cls != BaseNode)
    except TypeError:
        return False

@dataclass
class NodeErrorInfo:
    """Error information for a Haywire node operation"""
    error: str
    error_message: str
    note: list = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def add_note(self, note: str):
        """Add a note to the error info"""
        self.note.append(note)

@dataclass
class NodeIdentity:
    """Core identifying attributes of a node"""
    label: str = 'Node Name'
    description: str = 'Node Description'
    search_tags: list[str] = field(default_factory=lambda: ['add', 'sub', 'math', 'vector'])
    menu: str = 'misc/custom'
    help_md: str | None = None
    help_url: str = 'https://haywire.io/docs/node-help'
    registry_key: str = ''  # Set by registry during registration

@dataclass
class NodeBehavior:
    """Behavioral configuration of a node"""
    is_control_node: bool = False
    is_data_node: bool = True
    is_loopback_node: bool = False
    is_mutable: bool = False
    allows_variables: bool = False
    mute_connection: list[str] = field(default_factory=lambda: ['control_in_ID', 'control_out_ID'])

@dataclass
class NodeUIConfig:
    """UI configuration and capabilities"""
    is_collapsable: bool = True
    is_condensable: bool = True
    default_color: str = '#FFFFFF'
    icon: str | None = None
    node_renderer: str | None = None
    props_renderer: str | None = None
    custom_gui: str | None = None

@dataclass
class NodeUIState:
    """Runtime UI state"""
    is_muted: bool = False
    is_collapsed: bool = False
    is_condensed: bool = False
    is_pinned: bool = False
    custom_color: str = '#000000'
    posX: float = 0
    posY: float = 0
    width: float = 100
    height: float = 100
    width_min: float = -1
    height_min: float = -1

@dataclass
class NodeMetadata:
    """User-defined metadata"""
    notes: list[str] = field(default_factory=list)
    custom: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Node Identity Decorator and Metaclass
# ============================================================================

def node_identity(label: str, description: str = '', search_tags: list[str] = None, 
                 menu: str = 'misc/custom', help_md: str = None, 
                 help_url: str = 'https://haywire.io/docs/node-help'):
    """Decorator to attach node metadata"""
    def decorator(cls):
        cls.class_identity = NodeIdentity(
            label=label,
            description=description,
            search_tags=search_tags or [],
            menu=menu,
            help_md=help_md,
            help_url=help_url
        )
        return cls
    return decorator

class NodeMeta(type):
    """Metaclass that processes pin declarations"""
    
    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)
        
        # Collect PinSpecs from class attributes
        pin_specs = {}
        for attr_name, attr_value in attrs.items():
            if isinstance(attr_value, PinSpec):
                pin_specs[attr_name] = attr_value
        
        original_init = new_class.__init__
        
        def enhanced_init(self, *args, **kwargs):
            # Initialize storage dictionaries
            self.configs = {}
            self.properties = {}

            
            # Call original init
            original_init(self, *args, **kwargs)
            
            # Create static pins from class-level PinSpecs
            for attr_name, pin_spec in pin_specs.items():

                # Route to appropriate storage
                if pin_spec.is_config:
                    pin = pin_spec.create_inlet(attr_name)
                    self.configs[attr_name] = pin
                elif pin_spec.is_property:
                    pin = pin_spec.create_inlet(attr_name)
                    self.properties[attr_name] = pin
                elif pin_spec.flow_type in (FlowType.CTRL, FlowType.DATA, FlowType.CALLBACK):
                    pin = pin_spec.create_inlet(attr_name)
                    self.inlets[attr_name] = pin
                else:
                    pin = pin_spec.create_outlet(attr_name)
                    self.outlets[attr_name] = pin
                
                setattr(self, attr_name, pin)
            
            self._cache_dirty = True
            
            # Copy class identity
            if hasattr(self.__class__, 'class_identity'):
                from copy import deepcopy
                self.identity = deepcopy(self.__class__.class_identity)
        
        new_class.__init__ = enhanced_init
        return new_class


@abstractmethod
class NodeData():
    """Main data structure for a Haywire node"""
    def __init__(self):
        self.inlets: Dict[str, Inlet] = {}
        self.outlets: Dict[str, Outlet] = {}
        
        # Performance optimization: direct access caches
        # self._inlet_data_cache: dict[str, Any] = {}
        # self._cache_dirty = True
       
    def add_inlet(self, inlet: Inlet) -> Inlet:
        """Add an inlet element"""
        if '__' in inlet.id:
            # Handle special case for inlet IDs containing '__' - reserved to split concatenated attributes
            raise ValueError("Inlet ID cannot contain double underscores '__'")
        self.inlets[inlet.id] = inlet
        self._cache_dirty = True        
        return inlet
    
    def add_outlet(self, outlet: Outlet) -> Outlet:
        """Add an outlet element"""
        if '__' in outlet.id:
            # Handle special case for outlet IDs containing '__' - reserved to split concatenated attributes
            raise ValueError("Outlet ID cannot contain double underscores '__'")
        self.outlets[outlet.id] = outlet
        return outlet
        

@abstractmethod
class BaseNode(NodeData, metaclass=NodeMeta):
    """Base class combining HaywireNode requirements with NodeData"""
    
    def __init__(self, node_id: str, graph: Any):
        super().__init__()
        self.node_id = node_id
        self.graph = graph
        self.error_info: NodeErrorInfo | None = None
        
        # Organized attribute groups
        self.library: LibraryMetadata | None = None  # Set during registration
        self.identity = NodeIdentity()  # Will be overridden by metaclass if class_identity exists
        self.behavior = NodeBehavior()
        self.ui_config = NodeUIConfig()
        self.ui_state = NodeUIState()
        self.metadata = NodeMetadata()


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


