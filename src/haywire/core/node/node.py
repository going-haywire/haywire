from __future__ import annotations
import inspect
from copy import deepcopy
from typing import Any, Callable, Dict, List, Type, TypeVar, Optional, Union
from abc import abstractmethod
from dataclasses import dataclass, field

from haywire.core.data.enums import FlowType
from haywire.core.node.dataclasses import NodeBehavior, NodeErrorInfo, NodeUIConfig, NodeUIState, NodeUserMetadata

T = TypeVar('T')

from .ports import PortInlet, PortOutlet, PinSpec
from ..library.library_identity import LibraryIdentity
from ..data.specs import DataPortSpec


def is_node(cls):
    """Check if a class is a valid Haywire node class."""
    try:
        return (inspect.isclass(cls) and
                issubclass(cls, BaseNode) and
                cls != BaseNode)
    except TypeError:
        return False

@dataclass
class NodeIdentity:
    """Core identifying attributes of a node"""
    registry_id: str = ''  # Set by user for unique ID within library - fallback to class name
    registry_key: str = ''  # Set by registry during registration. combination of library-registry-id and node-registry-id.
    label: str = 'Node Name'
    description: str = 'Node Description'
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
        registry_key (str, optional): Full registry key (library + node ID). Usually set by registry.
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
        
        return new_class

@abstractmethod
class NodeData():
    """Main data structure for a Haywire node"""
    def __init__(self):
        """Initialize all pins from class definitions"""
        self.configs = {}
        self.properties = {}
        self.inlets: Dict[str, PortInlet] = {}
        self.outlets: Dict[str, PortOutlet] = {}
        
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
    def add_inlet(self, inlet: PortInlet) -> PortInlet:
        """Add an inlet element"""
        if '__' in inlet.id:
            # Handle special case for inlet IDs containing '__' - reserved to split concatenated attributes
            raise ValueError("Inlet ID cannot contain double underscores '__'")
        self.inlets[inlet.id] = inlet
        self._cache_dirty = True        
        return inlet
    
    #deprecated methods for dynamic pin management
    def add_outlet(self, outlet: PortOutlet) -> PortOutlet:
        """Add an outlet element"""
        if '__' in outlet.id:
            # Handle special case for outlet IDs containing '__' - reserved to split concatenated attributes
            raise ValueError("Outlet ID cannot contain double underscores '__'")
        self.outlets[outlet.id] = outlet
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

