"""
Pooled Compound Type - Final Simplified Version

Key changes:
1. Uses hooks from IType (_validate_port_type, _configure_port)
2. _validate_port_type: Prevents outlet creation
3. _configure_port: Sets allow_multiple_connections = True
4. Clean and focused - just overrides what's needed
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, TypeVar

from haywire.core.types import type, FlowType, CompoundType, DataField

T = TypeVar('T')

# ============================================================================
# TYPE DEFINITION
# ============================================================================

@type(
    registry_id='pooled',
    label='Pooled',
    description='Multi-source aggregation',
    color='#9c27b0',
    default={'value': {}},
)
class PooledType(CompoundType[T]):
    """
    Pooled compound type for multi-source aggregation.
    
    Pooled inlets accept connections from multiple upstream nodes
    and aggregate their values into a dictionary keyed by source ID.
    
    Usage:
        # Pooled floats
        PooledType[FLOAT].as_inlet(id='values')
        
        # Pooled meshes
        PooledType[MeshData].as_inlet(id='mesh_collection')
    
    Note: Pooled is INLET-ONLY - cannot be used with outlets!

    It sets the pin to allow multiple connections automatically. 

    IMPORTANT:
    It inherits the element type's flow type (if it is set). 
    !!Setting the flow type in the decorator or as_inlet/as_outlet has no effect!!
    
    Storage: PooledField stores Dict[str, T] with unwrapped values
    Worker Access: Dict[str, T] or List[T]
    
    Hooks:
    - _validate_port_type: Overridden to prevent outlets
    - _configure_port: Overridden to set allow_multiple_connections
    """
    
    field_class = None  # Will be set to PooledField after it's defined
    
    # ========================================================================
    # HOOKS - Override to customize behavior
    # ========================================================================
    

    @classmethod
    def _validate_port_type(cls, port_type: str) -> None:
        """
        Override: Pooled only supports inlets.
        
        Pooled fields aggregate multiple inputs - they can't be outputs.
        """
        if port_type == 'outlet':
            raise ValueError(
                "PooledType cannot be used with outlets. "
                "Pooled fields are for aggregating multiple inputs only."
            )
        # inlet and config are allowed (no error)
    
    @classmethod
    def _configure_port(cls, port, **context) -> None:
        """
        Override: Mark port as accepting multiple connections.
        
        This is the semantic purpose of pooled - to aggregate from
        multiple sources into one inlet.
        """
        port.allow_multiple_connections = True

        # pooled type's flow type is determined by its element type
        if not port.type_cls.element_type_cls:
            return
        
        # Start with the immediate element type
        current_type = port.type_cls.element_type_cls
        
        # Drill down until we find a non-NONE flow type
        while current_type is not None:
            # Check if this type has a non-NONE flow type
            if hasattr(current_type, 'class_identity'):
                if current_type.class_identity.flow_type != FlowType.NONE:
                    port.flow_type = current_type.class_identity.flow_type
                    return
                        
                # Move to next level if available
                if hasattr(current_type, 'element_type_cls'):
                    current_type = current_type.element_type_cls
                else:
                    break

    @property
    def value(self):
        """Pooled types don't have instances - this is for type checking only"""
        raise NotImplementedError("PooledType is a type descriptor, not instantiable")


# ============================================================================
# FIELD DEFINITION
# ============================================================================

@dataclass
class PooledField(DataField):
    """
    Field implementation for PooledType.
    
    Stores dict of source_id -> unwrapped value.
    Essential for multi-source aggregation where each source
    needs to be tracked and can be updated independently.
    
    Storage: Dict[str, T] where T is unwrapped (42.0 not FLOAT(42.0))
    Worker Access: Dict[str, T] or List[T]
    Transfer: Not allowed (inlet-only)
    """
    
    _sources: Dict[str, T] = field(default_factory=dict, init=False, repr=False)
    _default_kwargs: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize pooled field."""
        super().__post_init__()
        
        # Initialize from default if provided
        initial_dict = self._default_kwargs.get('value', {})
        if initial_dict:
            self._sources = {k: self._unwrap_value(v) for k, v in initial_dict.items()}
        else:
            self._sources = {}
        
    def get_value(self) -> Dict[str, T]:
        """
        Get dict of all source values.
        
        Returns:
            {"node1": 42.0, "node2": 15.0}  # Primitives unwrapped
            or
            {"node1": MeshData(...), "node2": MeshData(...)}  # Complex as-is
        """
        return dict(self._sources)
    
    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """
        Set value from a specific source.
        
        Source tracking is ESSENTIAL for pooled fields:
        - Each upstream node has a unique source_id
        - Values can be updated per-source
        - Sources can be disconnected individually
        
        Examples:
            # From node1:
            field.set_value(FLOAT(42.0), source_id="node1")
            # Stored: {"node1": 42.0}
            
            # From node2:
            field.set_value(FLOAT(15.0), source_id="node2")
            # Stored: {"node1": 42.0, "node2": 15.0}
            
            # Update from node1:
            field.set_value(FLOAT(99.0), source_id="node1")
            # Stored: {"node1": 99.0, "node2": 15.0}
        """
        if source_id is None:
            raise ValueError("PooledField requires source_id")
                
        # Check if value actually changed
        if self._sources.get(source_id) == value:
            return
        
        # Update source
        self._sources[source_id] = value
        self.is_dirty = True
        if self.on_changed.has_observers():
            self.fire(dict(self._sources))
        
    def get_stored_type(self) -> type:
        # other than most other fields, pooled field actually stores the element type
        return self.type_cls.element_type_cls
    
    def reset(self) -> None:
        """Clear all sources"""
        self._sources.clear()
        self.is_dirty = True
    
    def has_data(self) -> bool:
        """Check if has any sources"""
        return len(self._sources) > 0
    
    # ========================================================================
    # POOLED-SPECIFIC HELPERS
    # ========================================================================
    
    def remove_source(self, source_id: str) -> None:
        """
        Remove a disconnected source.
        
        Args:
            source_id: Node ID to remove
        """
        if source_id in self._sources:
            del self._sources[source_id]
            self.is_dirty = True
            self.fire(dict(self._sources))
    
    def get_values_list(self) -> List[T]:
        """
        Get values as list (for iteration).
        
        Returns:
            [42.0, 15.0]
        """
        return list(self._sources.values())
    
    def get_source_ids(self) -> List[str]:
        """
        Get list of source node IDs.
        
        Returns:
            ["node1", "node2"]
        """
        return list(self._sources.keys())


# Set field_class now that PooledField is defined
PooledType.field_class = PooledField
