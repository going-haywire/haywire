from __future__ import annotations
from typing import Any, Type
from dataclasses import dataclass, field, replace

from haywire.core.data.fields import SingleField, PooledField, DataField
from haywire.core.library.utils import derive_library_id, reg_key

from .enums import ContainerType

@dataclass
class DataPortSpec:
    """Defines the specification for a data field.

    Unified specification for both built-in and custom data types.
    Provides metadata about type, UI presentation, default values, and structure hints.

    Attributes:
        key: Registry key identifier (e.g., 'core:float', 'mylib:mesh_data')
        cls_type: The Python class (int, float, str, bool, bytes, dict, list, or custom class)
        label: Human-readable label
        description: Detailed description
        color: Pin color in graph UI (hex format)
        icon: Pin icon/shape name
        widget: Suggested UI widget for editing
        container_type: The data structure container (e.g., SINGLE, LIST)
        default: The default value for the field
        ui: Dictionary for extra UI-specific configurations
    """
    id: str
    cls_type: Type | None
    key: str = ''
    container_type: ContainerType = ContainerType.SINGLE
    label: str = ''
    description: str = ''
    color: str = '#757575'  # Default gray
    icon: str = 'circle'
    widget: str | None = None
    default: Any = None
    ui: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate default values for optional fields after initialization."""
        # Auto-generate key from id if not provided
        if not self.key:
            self.key = 'default:' + self.id

        # Auto-generate label from id if not provided
        if not self.label:
            self.label = self.id.replace('_', ' ').title()
                
        # Ensure description is a string
        if not self.description:
            self.description = self.id.replace('_', ' ')
                
        # Set smart defaults for value based on type and container
        if self.default is None and self.cls_type is not None:
            if self.container_type == ContainerType.SINGLE:
                if self.cls_type == float:
                    self.default = 0.0
                elif self.cls_type == int:
                    self.default = 0
                elif self.cls_type == bool:
                    self.default = False
                elif self.cls_type == str:
                    self.default = ""
                elif self.cls_type == bytes:
                    self.default = b""
                else:
                    # For custom types or other types, leave as None
                    self.default = None
            elif self.container_type in [ContainerType.LIST, ContainerType.SET]:
                self.default = []
            elif self.container_type == ContainerType.DICT:
                self.default = {}


    def __call__(self, **kwargs: Any) -> DataPortSpec:
        """Create a new instance with overridden attributes."""
        return replace(self, **kwargs)
    
    def as_inlet(self, id: str, flow_type: 'FlowType' = None, **kwargs) -> 'PortInlet':
        """Convert this spec to a PortInlet, inheriting all spec attributes.
        
        Args:
            id: Unique identifier for the inlet
            flow_type: Type of flow (defaults to FlowType.DATA)
            **kwargs: Overrides for any spec attributes (label, widget, ui, etc.)
                     Also accepts inlet-specific args (callback, is_pooled, etc.)
                     Note: kwargs completely override spec values (no merging)
        
        Returns:
            PortInlet instance with all spec attributes merged
        """
        from dataclasses import asdict
        from ..data.enums import FlowType as FlowTypeEnum
        
        # Import here to avoid circular dependency
        from ..node.ports import PortInlet
        
        # Default flow_type if not provided
        if flow_type is None:
            flow_type = FlowTypeEnum.DATA
        
        # Start with all spec attributes
        spec_dict = asdict(self)
        
        # Build inlet kwargs: spec as base, then overrides
        inlet_kwargs = {
            **spec_dict,     # All spec attributes become part of the inlet
            'id': id,        # Override the id
            'flow_type': flow_type,
            **kwargs         # Any other overrides (callback, is_pooled, ui, etc.)
        }
        
        return PortInlet(**inlet_kwargs)
    
    def as_outlet(self, id: str, flow_type: 'FlowType' = None, **kwargs) -> 'PortOutlet':
        """Convert this spec to a PortOutlet, inheriting all spec attributes.
        
        Args:
            id: Unique identifier for the outlet
            flow_type: Type of flow (defaults to FlowType.DATA)
            **kwargs: Overrides for any spec attributes (label, widget, ui, etc.)
                     Note: kwargs completely override spec values (no merging)
        
        Returns:
            PortOutlet instance with all spec attributes merged
        """
        from dataclasses import asdict
        from ..data.enums import FlowType as FlowTypeEnum
        
        # Import here to avoid circular dependency
        from ..node.ports import PortOutlet
        
        # Default flow_type if not provided
        if flow_type is None:
            flow_type = FlowTypeEnum.DATA
        
        # Start with all spec attributes
        spec_dict = asdict(self)
        
        # Build outlet kwargs: spec as base, then overrides
        outlet_kwargs = {
            **spec_dict,     # All spec attributes become part of the outlet
            'id': id,        # Override the id
            'flow_type': flow_type,
            **kwargs         # Any other overrides (ui, etc.)
        }
        
        return PortOutlet(**outlet_kwargs)
    
    def as_config(self, id: str, callback=None, **kwargs) -> 'PortInlet':
        """Convert to config (no pin visible).
        
        Args:
            id: Unique identifier for the config
            callback: Optional callback function triggered on value change
            **kwargs: Overrides for any spec attributes
        
        Returns:
            PortInlet with FlowType.NONE
        """
        from ..data.enums import FlowType as FlowTypeEnum
        return self.as_inlet(id, flow_type=FlowTypeEnum.NONE, callback=callback, **kwargs)


class DataFieldFactory:
    """Separate factory concerns"""
    @staticmethod
    def create(spec: DataPortSpec, is_pooled: bool = False) -> DataField:
        """Create appropriate DataField instance based on pooled flag"""
        if is_pooled:
            return PooledField(
                type=spec.cls_type,
                value={},
                is_pooled=True
            )
        else:
            return SingleField(
                type=spec.cls_type,
                value=spec.default,
                is_pooled=False
            )


def specs_factory(**kwargs: Any) -> DataPortSpec:
    """Factory function to create a DataFieldSpec instance.

    This allows creating a template spec and then calling it to produce
    configured instances.

    Example:
        INT = specs_factory(value_type=int)
        my_int_field = INT(value=10)
    """
    return DataPortSpec(**kwargs)
