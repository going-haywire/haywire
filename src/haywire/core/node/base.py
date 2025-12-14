from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, Dict, Type, TypeVar, Union
from abc import abstractmethod
from dataclasses import dataclass, field, asdict

from ..registry.identity import BaseIdentity
from ..library.utils import derive_library_identity, reg_key
from ..library.identity import LibraryIdentity
from ..types.ports import DataPort, PortInlet, PortOutlet
from .dataclasses import (
    NodeBehavior, 
    NodeErrorInfo, 
    NodeUIConfig, 
    NodeUIState, 
    NodeUserMetadata
)

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



class NodeMeta(type):
    """Metaclass for nodes"""
    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)
        return new_class


class NodeData:
    """Node data management with port collections"""
    
    def __init__(self):
        """Initialize port collections"""
        self.configs: Dict[str, DataPort] = {}
        self.properties: Dict[str, DataPort] = {}
        self.inlets: Dict[str, PortInlet] = {}
        self.outlets: Dict[str, PortOutlet] = {}
        self._cache_dirty = True
    
    def add(self, port: DataPort) -> DataPort:
        """
        Add a port (inlet or outlet) to the node.
        
        Args:
            port: DataPort to add (PortInlet or PortOutlet)
        
        Returns:
            The added port
        
        Raises:
            ValueError: If port ID already exists
        """
        if port.is_inlet():
            inlet = port  # type: PortInlet
            if inlet.id in self.inlets:
                raise ValueError(f"Inlet ID already exists: {inlet.id}")
            self.inlets[inlet.id] = inlet
            self._cache_dirty = True
            return inlet
        else:
            outlet = port  # type: PortOutlet
            if outlet.id in self.outlets:
                raise ValueError(f"Outlet ID already exists: {outlet.id}")
            self.outlets[outlet.id] = outlet
            self._cache_dirty = True
            return outlet
    
    def inlet(self, id: str) -> Any:
        """
        Get the unwrapped value of an inlet for worker access.
        
        This is the primary method workers use to read inlet values.
        Returns data in its most convenient form:
        - PrimitiveField: Unwrapped primitive (42.0, "hello")
        - BaseField: BaseType instance (MeshData(...))
        - PooledField: Dict[str, T] of unwrapped values
        - ArrayField: List[T] of unwrapped values
        
        Args:
            id: The ID of the inlet
        
        Returns:
            Unwrapped value appropriate for the field type
        
        Examples:
            # Primitive inlet
            value = self.inlet('float_input')  # Returns: 42.0
            
            # Complex inlet
            mesh = self.inlet('mesh_input')  # Returns: MeshData(...)
            
            # Pooled inlet
            temps = self.inlet('temperature_pool')  # Returns: {"node1": 20.0, "node2": 25.0}
            
            # Array inlet
            numbers = self.inlet('number_array')  # Returns: [1.0, 2.0, 3.0]
        """
        inlet = self.inlets.get(id)
        if not inlet:
            raise KeyError(f"Inlet '{id}' not found")
        
        return inlet.get_value()
    
    def outlet_value(self, id: str) -> Any:
        """
        Get the unwrapped value of an outlet.
        
        Useful for debugging or when a node needs to read its own output.
        
        Args:
            id: The ID of the outlet
        
        Returns:
            Unwrapped value
        """
        outlet = self.outlets.get(id)
        if not outlet:
            raise KeyError(f"Outlet '{id}' not found")
        
        return outlet.get_value()
    
    def set_outlet(self, id: str, value: Any) -> None:
        """
        Set the value of an outlet from worker.
        
        This is the primary method workers use to write output values.
        Accepts unwrapped values - no need to wrap in IType!
        
        Args:
            id: The ID of the outlet
            value: Unwrapped value to set
        
        Examples:
            # Primitive outlet
            self.set_outlet('result', 42.0)  # Just pass the float!
            
            # Complex outlet
            self.set_outlet('mesh_out', MeshData(...))  # Pass the instance
            
            # Array outlet
            self.set_outlet('sorted', [1.0, 2.0, 3.0])  # Pass the list
        """
        outlet = self.outlets.get(id)
        if not outlet:
            raise KeyError(f"Outlet '{id}' not found")
        
        outlet.set_value(value)


class BaseNode(NodeData, metaclass=NodeMeta):
    """
    Base class for all Haywire nodes.
    
    Combines NodeData (port management) with node lifecycle and execution.
    Subclasses must implement the worker() method for execution logic.
    
    The new architecture provides clean API:
    - inlet(id) - Get unwrapped value
    - set_outlet(id, value) - Set unwrapped value
    - No manual wrapping/unwrapping needed!
    """
    
    def __init__(self, node_id: str, wrapper: 'NodeWrapper'):
        """
        Initialize node.
        
        Args:
            node_id: Unique identifier for this node instance
            wrapper: NodeWrapper managing this node
        """
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
        """Get node identity from class"""
        return self.__class__.class_identity
    
    @property
    def library(self) -> LibraryIdentity:
        """Get library identity from class"""
        return self.__class__.class_library
    
    @abstractmethod
    def worker(self, context: dict) -> dict | None:
        """
        The main execution logic of the node.
        
        Override this method in subclasses to implement node behavior.
        
        Args:
            context: Execution context dictionary
        
        Returns:
            Optional dict with execution results
        
        Example:
            def worker(self, context: dict) -> dict | None:
                # Read inlet values (already unwrapped!)
                a = self.inlet('input_a')  # 5.0
                b = self.inlet('input_b')  # 3.0
                
                # Compute result
                result = a + b  # 8.0
                
                # Set outlet (no wrapping needed!)
                self.set_outlet('result', result)
                
                return None
        """
        pass
    
    def to_dict(self) -> dict:
        """
        Serialize node to dictionary.
        
        Returns:
            Dict representation of the node
        """
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