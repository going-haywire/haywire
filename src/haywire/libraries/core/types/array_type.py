"""
Array Compound Type - Final Simplified Version

Key changes:
1. Uses hooks from IType (_validate_port_type, _configure_port)
2. No special port attribute setting (uses defaults from CompoundType)
3. Clean and minimal - just declares field_class
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, TypeVar

from haywire.core.types.base import CompoundType
from haywire.core.data.fields import DataField
from haywire.core.types.decorator import type
from haywire.core.data.enums import ContainerType, FlowType

T = TypeVar('T')

# ============================================================================
# TYPE DEFINITION
# ============================================================================

@type(
    registry_id='array',
    container_type=ContainerType.LIST,
    flow_type=FlowType.DATA,
    label='Array',
    description='Homogeneous typed array',
    color='#e91e63',
    icon='list',
    widget=None,
    default={'value': []},
)
class ArrayType(CompoundType[T]):
    """
    Homogeneous typed array compound type.
    
    Arrays store lists of elements of a specific type.
    All elements must be the same type (or compatible via adapters).
    
    Usage:
        # Array of floats
        ArrayType[FLOAT].as_inlet(id='numbers', default=[1.0, 2.0, 3.0])
        
        # Array of meshes
        ArrayType[MeshData].as_outlet(id='meshes')
    
    Storage: ArrayField stores List[T] with unwrapped elements
    Transfer: List of unwrapped values (primitives or instances)
    
    Hooks: Uses default implementations from IType
    - _validate_port_type: Allows all port types (inlet, outlet, config)
    - _configure_port: No special configuration needed
    """
    
    field_class = None  # Will be set to ArrayField after it's defined
    
    # No hook overrides needed - uses defaults from IType!
    # Allows inlets, outlets, and configs
    # No special port configuration
    
    @property
    def value(self):
        """Arrays don't have instances - this is for type checking only"""
        raise NotImplementedError("ArrayType is a type descriptor, not instantiable")


# ============================================================================
# FIELD DEFINITION
# ============================================================================

@dataclass
class ArrayField(DataField):
    """
    Field implementation for ArrayType.
    
    Stores list of unwrapped values with element type tracking.
    
    Storage: List[T] where T is unwrapped (42.0 not FLOAT(42.0))
    Worker Access: List[T] (unwrapped primitives or instances)
    Transfer: List[T] (unwrapped)
    """
    
    _items: List[T] = field(default_factory=list, init=False, repr=False)
 
    def __post_init__(self):
        """Initialize complex field with default instance"""
        super().__post_init__()
        
        # Initialize from default
        initial_list = self.default_kwargs.get('value', [])
        self._items = initial_list
            
    def get_value(self) -> List[T]:
        """
        Get list for worker access.
        
        Returns:
            [42.0, 3.14, 27.5]  # Primitives unwrapped
            or
            [MeshData(...), MeshData(...)]  # Complex types as-is
        """
        return list(self._items)
    
    def set_value(self, value: Any, source_id: str | None = None) -> None:
        """
        Set array from connection or programmatic update.
        
        Examples:
            # From connection (list of instances):
            field.set_value([FLOAT(1), FLOAT(2), FLOAT(3)])
            # Stored: [1.0, 2.0, 3.0]
            
            # Programmatic (already unwrapped):
            field.set_value([1.0, 2.0, 3.0])
            # Stored: [1.0, 2.0, 3.0]
        """
        if not isinstance(value, list):
            raise TypeError(f"ArrayField requires list, got {type(value).__name__}")
        
        self._items = value
        self.is_dirty = True
        self.fire(list(self._items))
    
    def reset(self) -> None:
        """Reset to default array"""
        initial_list = self.default_kwargs.get('value', [])
        self._items = self._unwrap_items(initial_list)
        self.is_dirty = True
    
    def has_data(self) -> bool:
        """Check if has any items"""
        return len(self._items) > 0
    
    # ========================================================================
    # ARRAY-SPECIFIC HELPERS
    # ========================================================================
    
    def get_item(self, index: int) -> T:
        """Get specific item by index"""
        return self._items[index]
    
    def __len__(self) -> int:
        """Get array length"""
        return len(self._items)


# Set field_class now that ArrayField is defined
ArrayType.field_class = ArrayField
