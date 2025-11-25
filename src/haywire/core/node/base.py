from __future__ import annotations
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Type, TypeVar, Optional, Union
from abc import abstractmethod
from dataclasses import dataclass, field

from ..data.enums import FlowType
from ..data.specs import DataPortSpec
from ..registry.identity import BaseIdentity
from ..library.utils import derive_library_identity, reg_key
from ..library.identity import LibraryIdentity
from ..types.ports import DataPort, PortInlet, PortOutlet
from .dataclasses import NodeBehavior, NodeErrorInfo, NodeUIConfig, NodeUIState, NodeUserMetadata

if TYPE_CHECKING:
    from haywire.core.node.node_wrapper import NodeWrapper

T = TypeVar('T')

@dataclass
class NodeIdentity(BaseIdentity):
    """Core identifying attributes of a node"""
    search_tags: list[str] = field(default_factory=lambda: ['add', 'sub', 'math', 'vector'])
    menu: str = 'misc/custom'
    help_md: str | None = None
    help_url: str = 'https://haywire.io/docs/node-help',
    _is_error: bool = False,
    _error_priority: int = 0


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
        _is_error (bool, optional): Whether this node handles error cases.
            Defaults to False. Only one error node can be registered. 
        _error_priority (int, optional): Priority of this error node when multiple are registered.
            If multiple error nodes are registered, 
            the one with the higher _error_priority will override the previous ones.
    
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
            _is_error=False
        )
        class CustomNode(BaseNode): ...

        # Error handling node
        @node(_is_error=True, label="Error Handler", menu="system/errors")
        class ErrorNode(BaseNode): ...
    """
    def decorator(inner_cls: Type[T]) -> Type[T]:
        if not issubclass(inner_cls, BaseNode):
            raise TypeError(f"@node can only be applied to BaseNode subclasses, got {inner_cls}")

        # Set defaults from class name if not provided
        kwargs.setdefault('registry_id', inner_cls.__name__)
        kwargs.setdefault('label', inner_cls.__name__)
        
        # Get library identity (survives hot-reload)
        library_identity = derive_library_identity(inner_cls)
        
        # Auto-derive registry_key
        library_id = library_identity.id if library_identity else None
        kwargs['registry_key'] = reg_key(library_id, 'node', kwargs['registry_id'])
        
        # Create and attach identity and library
        inner_cls.class_identity = NodeIdentity(**kwargs)
        inner_cls.class_library = library_identity
        return inner_cls

    return decorator if cls is None else decorator(cls)


# ============================================================================
# Node Metaclass
# ============================================================================

class NodeMeta(type):    
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
        self._cache_dirty = True

    def add(self, port: DataPort) -> DataPort:
        """Add an Port Element (inlet or outlet) to the node."""
        if port.is_inlet():
            inlet = port  # type: PortInlet
            if inlet.id in self.inlets:
                raise ValueError(f"Inlet ID already exists: {inlet.id}. Cannot add duplicate.")
            self.inlets[inlet.id] = inlet
            self._cache_dirty = True     
            return inlet   
        else:
            outlet = port  # type: PortOutlet
            if outlet.id in self.outlets:
                raise ValueError(f"Outlet ID already exists: {outlet.id}. Cannot add duplicate.")
            self.outlets[outlet.id] = outlet
            self._cache_dirty = True     
            return outlet
   
        
@abstractmethod
class BaseNode(NodeData, metaclass=NodeMeta):
    """Base class combining HaywireNode requirements with NodeData"""
    
    def __init__(self, node_id: str, wrapper: 'NodeWrapper'):
        super().__init__()
        self.node_id = node_id
        self.wrapper = wrapper
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

