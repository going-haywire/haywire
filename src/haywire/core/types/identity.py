"""
Data Port Identity - Unified identity for all data types.

This module provides the DataPortIdentity class which combines registry identity
with type specification for all data that can flow through ports.
"""

from dataclasses import dataclass, field
from typing import Any

from ..registry.identity import BaseIdentity
from ..data.enums import ContainerType, FlowType

from .interface import IType

@dataclass
class DataTypeIdentity(BaseIdentity):
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
    """
    # Inherited from BaseIdentity:
    # registry_id: str = ''
    # registry_key: str = ''
    # label: str = ''
    # description: str = ''
    
    # Override flow_type to make it required for ports
    container_type: str = ContainerType.SINGLE
    flow_type: FlowType = FlowType.NONE

    # Type specification:
    type_cls: IType = None  # The Python Type class
    default: dict = None
    
    # UI specification:
    color: str = '#757575'
    icon: str = 'circle'
    widget: str | None = None
    ui: dict[str, Any] = field(default_factory=dict)
    help_url: str = ''
    
    def __post_init__(self):
        """Auto-generate defaults for convenience."""        
        # Auto-generate label from registry_id
        if not self.label and self.registry_id:
            self.label = self.registry_id.replace('_', ' ').title()
        
        # Auto-generate description
        if not self.description and self.label:
            self.description = self.label
        

