"""
DataPort Class - Unified port for inlets and outlets.

This module provides the DataPort class that integrates with the DataField hierarchy.
Direction is determined by the is_inlet field (True for inlet, False for outlet).
"""

from __future__ import annotations
from dataclasses import MISSING, dataclass, field, fields
from typing import Any, Dict, Optional, TYPE_CHECKING

from haywire.core.data.enums import FlowType
from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.core.types.identity import DataTypeIdentity
from haywire.core.types.interface import IType
from haywire.core.types.utils import PortSpec, serialize_element_type

# Import the new DataField classes
from haywire.core.data.fields import DataField
from haywire.core.types.pipe import Pipes

if TYPE_CHECKING:
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.types.registry import TypeRegistry


@dataclass
class DataPort(DataTypeIdentity):
    """
    Unified port class for both inlets and outlets.
    
    Direction is determined by the `is_inlet` field:
    - is_inlet=True: Port receives data from connections (inlet)
    - is_inlet=False: Port sends data to connections (outlet)
    
    Adds runtime-specific fields on top of the identity:
    - id: Port identifier within the node
    - flow_type: CTRL, DATA, CALLBACK, or NONE
    - data: Runtime data field for storing values (created by type)
    - Connection state, element type, etc.
    
    Key simplification: Field is created by type.create_field(), not factory.
    
    Type tracking:
    - type_cls: The IType class (FLOAT, MeshData, ArrayType)
    - element_type_cls: For compound types, the element IType (FLOAT, MeshData)
    
    Hierarchical access:
        port.element_type_cls → FLOAT (for ArrayType[FLOAT])
        port.element_type_cls.element_type_cls → float (Python type)
    """
    
    # Port identifier within node (different from registry_id!)
    id: str = ''
        
    # Runtime data field (created by type in __post_init__)
    _data: Optional[DataField] = field(
        default=None, 
        metadata={'serialize': False})
    """DataField instance storing port data"""
    
    # Type tracking
    type_cls: type[IType] = field(
        default=None, 
        metadata={'serialize': False}) 
    """The type class (FLOAT, ArrayType, etc.)"""
    
    # Connection state
    _edge_wrappers: dict[str, EdgeWrapper] = field(
        default_factory=dict, 
        repr=False, 
        metadata={'serialize': False})
    """Dict of EdgeWrapper instances connected to this port, keyed by UUID"""

    # Outlet-specific
    _pipes: Optional[Pipes] = field(
        default=None, 
        repr=False, 
        metadata={'serialize': False}
    )

    allow_multiple_connections: bool = False  
    """Whether multiple connections are allowed"""

    # Direction flag
    is_inlet: bool = False
    """True for inlet, False for outlet"""

    # Inlet-specific
    use_mode: str = 'optional'
    is_lazy: bool = False
        
    # Internal: Store default override for field creation
    default: Optional[Dict[str, Any]] = field(default=None, repr=False)

    # ========================================================================
    # HIERARCHY & ORGANIZATION
    # ========================================================================
    
    parent_group: Optional[str] = None
    """ID of parent group port, None if top-level"""
    
    section: Optional[str] = None
    """Section name for property panel grouping"""
    
    order: int = 0
    """Display order within parent"""
    
    is_group: bool = False
    """True if this port is a group container"""
    
    is_section: bool = False
    """True if this is a section marker (not rendered in node)"""
    
    is_ghost: bool = False
    """True if this is a ghost pin for collapsed groups"""

    needs_loopback: bool = False
    """Set to True if the control flow from this outlet needs to loop back to the node"""
    
    _is_dirty_structural: bool = False
    """Internal flag to track if port link has structurally changed"""

    # ========================================================================
    # CALLBACKS
    # ========================================================================

    on_change: Optional[str] = None
    """Callback identifier to invoke when port value changes (e.g., 'reconfigure_ports')"""
    
    on_connect: Optional[str] = None
    """Callback identifier to invoke when connection is made"""
    
    on_disconnect: Optional[str] = None
    """Callback identifier to invoke when connection is broken"""

    # Runtime reference (not serialized)
    _wrapper: Optional['NodeWrapper'] = field(
        default=None, 
        repr=False, 
        metadata={'serialize': False}
    )
    
    def __post_init__(self):
        """
        Create data field via type.
        """
        # Skip parent's post_init for runtime ports

        if self.widget:
            if not isinstance(self.widget, dict):
                raise ValueError(
                    f"Attribute 'widget' is of type: {type(self.widget).__name__}, "
                    f"but must be a dict with 'key' and optional 'config' fields. "
                    "Use WidgetClass.config(**kwargs) to generate correct format."
                )
            # Parse new widget dict format: {'key': '...', 'config': {...}}
            if 'key' not in self.widget:
                raise ValueError(
                    "Attribute 'widget' is a dict and must contain the 'key' field. "
                    "Use WidgetClass.config(**kwargs) to generate correct format."
                )
            
            # Extract widget key and merge config into widget_config dict
            widget_key = self.widget['key']
            widget_config = self.widget.get('config', {})
            
            # Merge widget config into widget_config dict (widget config takes precedence)
            self.widget_config = {**self.widget_config, **widget_config}
            self.widget_key = widget_key

        # Create data field if needed
        if self._data is None and self.type_cls is not None:
            # Type creates its own field!
            self._data = self.type_cls.create_field(
                default_override=self.default
            )
        
        # Outlets allow multiple connections by default for data flow
        if self.is_outlet and self.flow_type == FlowType.DATA:
            self.allow_multiple_connections = True

    def _trigger_callback(self, callback_type: str, *args):
        """
        Trigger a callback by resolving the identifier.
        
        Examples:
            on_change='on_port_changed'  → nodeon_port_changed(port, old, new)
        """
        callback_name = getattr(self, callback_type)
        if not callback_name or not self._wrapper:
            return
        
        node = self._wrapper.node
        if hasattr(node, callback_name):
            method = getattr(node, callback_name)
            method(self, *args)
        else:
            raise ReferenceError(f"Node callback '{callback_name}' not found on node")

    def get_value(self) -> Any:
        """
        Get unwrapped value for worker convenience.
        
        Returns:
            - For PrimitiveField: Unwrapped primitive (42.0)
            - For BaseField: BaseType instance (MeshData(...))
            - For CompoundField: Container (dict, list, etc.)
            - None if no data
        """
        if not self._data:
            return None
        
        return self._data.get_value()
    
    def set_value(self, new_value: Any, connection_uuid: str | None = None) -> None:
        """
        Set value from connection or programmatic update.
        
        Args:
            new_value: Value to set (can be IType instance or raw value)
            source_id: Source identifier (required for pooled fields)
        """
        if not self._data:
            return
        
        self._data.set_value(new_value, source_id=connection_uuid)

        # Trigger on_change callback if value actually changed
        if self.on_change:
            self._trigger_callback('on_change', new_value)
        if self._pipes:
            self._pipes.propagate(new_value)
        if self.is_inlet:
            self._mark_as_data_dirty()

    def is_pin(self) -> bool:
        """
        Check if this is a visible pin (not a config)
        TODO: Not shure if this approach is correct
        """
        return self.flow_type != FlowType.NONE.value
    
    @property
    def is_outlet(self) -> bool:
        """Check if this is an outlet"""
        return not self.is_inlet
    
    def is_linked(self) -> bool:
        """Check if port has any linked edges"""
        return len(self._edge_wrappers) > 0

    def _add_link(self, edge_wrapper: EdgeWrapper) -> None:
        """
        Register a linked edge.
        If multiple links are not allowed, replaces existing.
        In addition, marks node as structurally dirty
        It triggers the on_connect callback.

        Args:
            edge_wrapper:  EdgeWrapper representing the link
        """
        if not edge_wrapper.connection_uuid in self._edge_wrappers:
            if not self.allow_multiple_connections:
                old_wrapper_uuid = next(iter(self._edge_wrappers), None)
                if old_wrapper_uuid:
                    self._clear_link(old_wrapper_uuid)
                self._edge_wrappers = {edge_wrapper.connection_uuid: edge_wrapper}
            else:
                self._edge_wrappers[edge_wrapper.connection_uuid] = edge_wrapper

            self._mark_as_structuraly_dirty()
            if self.on_connect:
                self._trigger_callback('on_connect', edge_wrapper)

    def _get_linked_edges_uuid(self) -> list[str]:
        """
        Get list of linked edge UUIDs.

        Returns:
            List of EdgeWrapper UUIDs linked to this port
        """
        return list(self._edge_wrappers.keys())

    def _is_linked_to(self, wrapper_uuid: str) -> bool:
        """
        Check if linked to given edge.
        Args:
            wrapper_uuid: UUID of EdgeWrapper to check
        Returns:
            True if linked, False otherwise
        """
        return wrapper_uuid in self._edge_wrappers
    
    def _clear_link(self, wrapper_uuid: str) -> None:
        """
        Remove a linked edge. 
        It clears the source from the data field.
        It also marks the node as structurally dirty.
        It triggers the on_disconnect callback.

        Args:
            wrapper_uuid: UUID of EdgeWrapper representing the link
        """
        if wrapper_uuid in self._edge_wrappers:
            edge_wrapper = self._edge_wrappers.pop(wrapper_uuid, None)
            self._data.remove_source(wrapper_uuid)
            self._mark_as_structuraly_dirty()

            if self.on_disconnect and edge_wrapper:
                self._trigger_callback('on_disconnect', edge_wrapper)

    def _clear_all_links(self) -> None:
        """
        Clear all linked edges. 
        Should only be called on cleanup operations.
        """
        self._edge_wrappers.clear()

    def get_valid_edges(self) -> list[EdgeWrapper]:
        """
        Get list of valid linked EdgeWrappers.

        Returns:
            List of valid EdgeWrapper instances linked to this port
        """
        return [
            edge_wrapper for edge_wrapper in self._edge_wrappers.values()
            if edge_wrapper.is_valid()
        ]

    def _mark_as_structuraly_dirty(self) -> None:
        """Mark the port's node as structurally dirty."""
        self._is_dirty_structural = True

    def _housekeeping(self) -> None:
        """
        Called during graph housekeeping phase.
        Rebuild connection pipes after structural changes (like reconnecting edges).
        This cannot be done immediately upon link changes since
        at the time of a link change, the edges are not yet validated.
        """
        if self._is_dirty_structural:
            self._refresh_pipes()
            # as soon as we refresh pipes, propagate current value
            if self._pipes:
                self._pipes.propagate(self.get_value())
        self._is_dirty_structural = False

    def _refresh_pipes(self) -> None:
        """
        Refresh pipes based on current link state.
        If outlet and linked, ensure pipes exist and are up-to-date.
        If outlet and unlinked, clear pipes.
        Called during graph housekeeping phase.
        """
        if self.is_outlet:
            if self.is_linked():
                if self._pipes is None:
                    self._pipes = Pipes()
                self._pipes.clear()
                for wrapper in self.get_valid_edges():
                    self._pipes.add_pipe(wrapper)
            else:
                if self._pipes:
                    self._pipes.clear()
                    self._pipes = None

    def _mark_as_data_dirty(self) -> None:
        """Mark the port's node as data dirty."""
        if self._wrapper:
            self._wrapper.mark_as_data_dirty()

    def is_callback_pin(self) -> bool:
        """Check if this is a callback pin"""
        return self.flow_type == FlowType.CALLBACK
    
    def is_control_pin(self) -> bool:
        """Check if this is a control pin"""
        return self.flow_type == FlowType.CONTROL
    
    def is_data_pin(self) -> bool:
        """Check if this is a data pin"""
        return self.flow_type == FlowType.DATA
    
    def get_control_outlets(self) -> bool:
        """Check if this port is a control outlet"""
        return self.flow_type == FlowType.CONTROL and self.is_outlet

    # ========================================================================
    # FACTORY
    # ========================================================================
    
    @classmethod
    def from_spec(
        cls, 
        spec: dict, 
        type_registry: 'TypeRegistry', 
        wrapper: 'NodeWrapper'
    ) -> 'DataPort':
        """
        Create a DataPort from a PortSpec dict.
        
        Resolves the type from the spec and creates a DataPort instance
        with wrapper reference available immediately.
        
        Note: CompoundType validation is done at spec creation time (as_inlet/as_outlet),
        so we trust the spec here.
        
        Args:
            spec: PortSpec from as_inlet/as_outlet/as_config or to_dict
            type_registry: Registry to resolve type classes
            wrapper: NodeWrapper to attach to the port
        
        Returns:
            Instantiated DataPort
        """
        kwargs = spec['kwargs'].copy()
        recipe = spec['recipe']

        # Resolve type class (handles compound types via element_type)
        type_cls = type_registry.resolve_type_from_spec(recipe)
        
        # Build port kwargs - spec already contains merged identity + user values
        flow_type = FlowType(kwargs.pop('flow_type', FlowType.DATA.value))
        
        port_kwargs = {
            **kwargs,                # Spec already has identity + user overrides
            'flow_type': flow_type,
            'type_cls': type_cls,
            '_wrapper': wrapper, 
        }
        
        # Create port
        port = cls(**port_kwargs)
        
        # Let type configure port (for compound types, etc.)
        type_cls._configure_port(port)
        
        return port
    
    def to_dict(self) -> dict:
        """Serialize port using field metadata for control"""
        result = {
            'kwargs': {},
            'recipe': serialize_element_type(self.type_cls)
        }
        
        # Iterate over dataclass fields
        for f in fields(self):
            # Skip fields marked as non-serializable
            if not f.metadata.get('serialize', True):
                continue
                
            value = getattr(self, f.name)
            
            # Skip if default value
            if f.default is not MISSING and value == f.default:
                continue
            if f.default_factory is not MISSING and value == f.default_factory():
                continue
            
            # Transform enums
            if isinstance(value, FlowType):
                value = value.value
                
            result['kwargs'][f.name] = value
        
        return result