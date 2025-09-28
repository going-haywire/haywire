from __future__ import annotations
import inspect
from typing import Any, Dict, List
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from .elements import Inlet, Outlet
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
    """Metaclass that automatically copies class_identity to instance identity"""
    def __new__(cls, name, bases, attrs):
        # Create the class normally
        new_class = super().__new__(cls, name, bases, attrs)
        
        # Store original __init__ method
        original_init = new_class.__init__
        
        def enhanced_init(self, *args, **kwargs):
            # Call original __init__
            original_init(self, *args, **kwargs)
            
            # Auto-copy class_identity to instance identity if it exists
            if hasattr(self.__class__, 'class_identity'):
                # Copy the dataclass to avoid shared references
                from copy import deepcopy
                self.identity = deepcopy(self.__class__.class_identity)
        
        # Replace the __init__ method
        new_class.__init__ = enhanced_init
        
        return new_class


@abstractmethod
class NodeData():
    """Main data structure for a Haywire node"""
    def __init__(self):
        self.inlets: Dict[str, Inlet] = {}
        self.outlets: Dict[str, Outlet] = {}
        
        # Performance optimization: direct access caches
        self._inlet_data_cache: dict[str, Any] = {}
        self._cache_dirty = True
       
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
    
    def get_inlet_value(self, inlet_id: str) -> Any:
        """Fast access to inlet value (cached)"""
        if self._cache_dirty:
            self._rebuild_cache()
        
        if inlet_id in self._inlet_data_cache:
            data = self._inlet_data_cache[inlet_id]
            return data.get_value()
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
            if outlet.data:
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
            'inlets': {k: v.to_dict() for k, v in self.inlets.items()},
            'outlets': {k: v.to_dict() for k, v in self.outlets.items()}
        }

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


