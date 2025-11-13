"""
Data Port Identity - Unified identity for all data types.

This module provides the DataPortIdentity class which combines registry identity
with type specification for all data that can flow through ports.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Type

from ..library.base_identity import BaseIdentity
from ..data.enums import ContainerType, FlowType

@dataclass
class DataPortIdentity(BaseIdentity):
    """
    Unified identity for all data types that can flow through ports.
    
    Combines:
    - Registry identity (registry_id, registry_key, label, description)
    - Type specification (cls, container_type, default)
    - UI metadata (color, icon, widget, ui)
    
    Used for:
    - Type variants (FLOAT, INT, Temperature) - primitive type wrappers
    - Custom types (MeshData, with to_dict/from_dict) - compound data structures
    
    Attributes:
        registry_id: Unique ID within library (e.g., 'float', 'temperature', 'mesh_data')
        registry_key: Full key with library (e.g., 'core:float', 'example:temperature')
        label: Display name
        description: Type description
        cls: Python type (int, float, str, MeshData, etc.)
        container_type: SINGLE, LIST, DICT, SET, TUPLE
        flow_type: DATA, CTRL, or NONE
        color: UI pin color (hex)
        icon: UI pin icon
        widget: Widget for editing values
        default: Default value for this type
        ui: Additional UI properties (dict)
        help_url: Documentation link
        _is_variant: True for type variants (primitive wrappers), False for custom types
    """
    # Inherited from BaseIdentity:
    # registry_id: str = ''
    # registry_key: str = ''
    # label: str = ''
    # description: str = ''
    
    # Override flow_type to make it required for ports
    flow_type: FlowType = FlowType.NONE

    # Type specification:
    cls: Type | None = None  # The Python class (int, float, MeshData, etc.)
    container_type: ContainerType = ContainerType.SINGLE
    default: Any = None
    
    # UI specification:
    color: str = '#757575'
    icon: str = 'circle'
    widget: str | None = None
    ui: dict[str, Any] = field(default_factory=dict)
    help_url: str = ''
    
    # Internal flags (set by decorators):
    _is_variant: bool = False  # True for type variants, False for custom types
    
    def __post_init__(self):
        """Auto-generate defaults for convenience."""        
        # Auto-generate label from registry_id
        if not self.label and self.registry_id:
            self.label = self.registry_id.replace('_', ' ').title()
        
        # Auto-generate description
        if not self.description and self.label:
            self.description = self.label
        
        # Set smart defaults based on cls
        if self.default is None and self.cls is not None:
            if self.container_type == ContainerType.SINGLE:
                if self.cls == float:
                    self.default = 0.0
                elif self.cls == int:
                    self.default = 0
                elif self.cls == bool:
                    self.default = False
                elif self.cls == str:
                    self.default = ""
                elif self.cls == bytes:
                    self.default = b""
                # Custom types get None as default
            elif self.container_type in [ContainerType.LIST, ContainerType.SET]:
                self.default = []
            elif self.container_type == ContainerType.DICT:
                self.default = {}

