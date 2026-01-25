"""
DataPort Classes - Updated to work with new DataField system

This module provides the DataPort, PortInlet, and PortOutlet classes
that integrate with the new DataField hierarchy.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from haywire.core.data.enums import FlowType
from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.identity import DataTypeIdentity
from haywire.core.types.interface import IType

# Import the new DataField classes
from haywire.core.data.fields import DataField
from haywire.core.types.pipe import Pipes
from haywire.core.types.registry import TypeRegistry


@dataclass
class DataPort(DataTypeIdentity):
    """
    Extended DataTypeIdentity with runtime port information.
    
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
    _data: Optional[DataField] = None
    """DataField instance storing port data"""
    
    # Type tracking
    type_cls: type[IType] = field(default=None, metadata={'serialize': False}) 
    """The type class (FLOAT, ArrayType, etc.)"""
    
    # Connection state
    _edge_wrappers: dict[str, EdgeWrapper] = field(
        default_factory=dict, 
        repr=False, 
        metadata={'serialize': False})
    """Dict of EdgeWrapper instances connected to this port, keyed by UUID"""
    allow_multiple_connections: bool = False  
    """Whether multiple connections are allowed"""
    
    # Inlet-specific
    use_mode: str = 'optional'
    is_lazy: bool = False
    
    # Outlet-specific
    _pipes: Optional[Pipes] = field(
        default=None, 
        repr=False, 
        metadata={'serialize': False}
    )
    
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
        if self.is_inlet():
            self._mark_as_data_dirty()

    def is_pin(self) -> bool:
        """
        Check if this is a visible pin (not a config)
        TODO: Not shure if this approach is correct
        """
        return self.flow_type != FlowType.NONE.value
    
    def is_inlet(self) -> bool:
        """Check if this is an inlet"""
        return False

    def is_outlet(self) -> bool:
        """Check if this is an outlet"""
        return False
    
    def is_linked(self) -> bool:
        """Check if port has any linked edges"""
        return len(self._edge_wrappers) > 0

    def _add_link(self, wrapper: EdgeWrapper) -> None:
        """
        Register a linked edge.
        If multiple links are not allowed, replaces existing.
        In addition, marks node as structurally dirty
        It triggers the on_connect callback.

        Args:
            wrapper:  EdgeWrapper representing the link
        """
        if not wrapper.connection_uuid in self._edge_wrappers:
            if not self.allow_multiple_connections:
                old_wrapper_uuid = next(iter(self._edge_wrappers), None)
                if old_wrapper_uuid:
                    self._clear_link(old_wrapper_uuid)
                self._edge_wrappers = {wrapper.connection_uuid: wrapper}
            else:
                self._edge_wrappers[wrapper.connection_uuid] = wrapper

            self._mark_as_structuraly_dirty()
            if self.on_connect:
                self._trigger_callback('on_connect', wrapper)

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
            wrapper = self._edge_wrappers.pop(wrapper_uuid, None)
            self._data.remove_source(wrapper_uuid)
            self._mark_as_structuraly_dirty()

            if self.on_disconnect and wrapper:
                self._trigger_callback('on_disconnect', wrapper)

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
            wrapper for wrapper in self._edge_wrappers.values()
            if wrapper.is_valid()
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
        if self.is_outlet():
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

    def to_dict(self) -> dict:
        """
        Serialize port to dict using recipe format.
        
        The recipe stores the original creation call that can be replayed
        during deserialization. Hierarchy fields are added to the recipe kwargs.
        
        Returns:
            Dict with recipe format including hierarchy information
        """
        if not hasattr(self, '_creation_recipe'):
            raise NotImplementedError(
                f"Port {self.id} has no _creation_recipe. "
                f"Port must be created via IType.as_inlet/as_outlet methods."
            )
        
        # Start with base recipe
        recipe = {
            'type': 'recipe',
            **self._creation_recipe
        }
        
        # Add hierarchy fields to kwargs (they'll be passed to port constructor)
        # Only include non-default values to keep serialization compact
        hierarchy_fields = {}
        
        if self.parent_group is not None:
            hierarchy_fields['parent_group'] = self.parent_group
        
        if self.section is not None:
            hierarchy_fields['section'] = self.section
        
        if self.order != 0:
            hierarchy_fields['order'] = self.order
        
        if self.is_group:
            hierarchy_fields['is_group'] = self.is_group
        
        if self.is_section:
            hierarchy_fields['is_section'] = self.is_section
        
        if self.is_ghost:
            hierarchy_fields['is_ghost'] = self.is_ghost
        
        # Merge hierarchy fields into kwargs
        if hierarchy_fields:
            recipe['kwargs'] = {
                **recipe['kwargs'],
                **hierarchy_fields
            }
        
        return recipe

    @classmethod
    def from_dict(
        cls, 
        data: dict, 
        type_registry: TypeRegistry
    ) -> 'PortInlet | PortOutlet':
        """
        Deserialize port from dict.
        
        Reconstructs the port by replaying the original creation call,
        including hierarchy information.
        
        Args:
            data: Serialized port data (from to_dict())
            type_registry: TypeRegistry to look up registered types
        
        Returns:
            Reconstructed PortInlet or PortOutlet with hierarchy preserved
        """
        from haywire.core.types.utils import _deserialize_type_spec
        
        if data.get('type') != 'recipe':
            raise ValueError(
                f"Unknown port serialization format: {data.get('type')}"
            )
        
        method_name = data['method']
        kwargs = data['kwargs'].copy()
        
        # Deserialize base type
        type_cls = _deserialize_type_spec(
            {'registry_key': data['registry_key']},
            type_registry
        )
        
        # Recursively deserialize element type if present (for compound types)
        if 'element_type' in data:
            element_type_cls = _deserialize_type_spec(
                data['element_type'],
                type_registry
            )
            # Parameterize: CompoundType[ElementType]
            parameterized = type_cls[element_type_cls]
            method = getattr(parameterized, method_name)
        else:
            # Simple type
            method = getattr(type_cls, method_name)
        
        # Extract id (required positional argument)
        port_id = kwargs.pop('id')
        
        # Recreate the port - hierarchy fields in kwargs are passed through
        # to the port constructor automatically!
        port = method(port_id, **kwargs)
        
        return port

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
        return (self.flow_type == FlowType.CONTROL and 
                self.is_outlet())
     
@dataclass
class PortInlet(DataPort):
    """Inlet port - can receive data from connections"""
    
    def is_inlet(self) -> bool:
        return True
    
    # __post_init__ inherited from DataPort


@dataclass
class PortOutlet(DataPort):
    """Outlet port - can send data to connections"""
    
    def is_outlet(self) -> bool:
        return True
    
   # __post_init__ inherited from DataPort
    def __post_init__(self):
        super().__post_init__()
        if self.flow_type == FlowType.DATA:
            self.allow_multiple_connections = True