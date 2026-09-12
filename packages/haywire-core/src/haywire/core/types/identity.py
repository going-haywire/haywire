"""
Data Port Identity - Unified identity for all data types.

This module provides the DataPortIdentity class which combines registry identity
with type specification for all data that can flow through ports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from haywire.core.types.enums import FlowType, StoreStrategy

from ..registry.identity import BaseIdentity

if TYPE_CHECKING:
    from haywire.core.types.interface import IType


@dataclass
class DataTypeIdentity(BaseIdentity):
    """
    Unified identity for all data types that can flow through ports.

    Combines:
    - Registry identity (registry_id, registry_key, label, description)
    - Type specification (cls, default)
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
        flow_type: DATA, CTRL, or NONE
        color: UI pin color (hex)
        icon: UI pin icon, used by any direction that declares none of its own
        icon_in: Icon for inlet pins, defaulting to ``icon``
        icon_in_multi: Icon for multi-link inlet pins, defaulting to ``icon_in``
        icon_out: Icon for outlet pins, defaulting to ``icon``
        icon_out_multi: Icon for multi-link outlet pins, defaulting to ``icon_out``
        widget: Widget for editing values
        default: Default value for this type
        store_strategy: when to serialize field values
        help_url: Documentation link
    """

    # Inherited from BaseIdentity:
    # registry_id: str = ''
    # registry_key: str = ''
    # label: str = ''
    # description: str = ''

    # Override flow_type to make it required for ports
    flow_type: FlowType = FlowType.NONE

    # Type specification:
    type_cls: type[IType] | None = None  # The Python Type class
    default: dict | None = None
    store_strategy: StoreStrategy = StoreStrategy.NONE
    """flag to control whether field values are serialized"""

    # UI specification:
    color: str = "#757575"
    icon: str | None = None
    icon_in: str | None = None
    icon_in_multi: str | None = None
    icon_out: str | None = None
    icon_out_multi: str | None = None

    widget_key: str | None = None
    widget_config: dict[str, Any] = field(default_factory=dict)

    help_url: str = ""

    def __post_init__(self):
        """Auto-generate defaults and parse widget config."""

        # Auto-generate label from registry_id
        if not self.label and self.registry_id:
            self.label = self.registry_id.replace("_", " ").title()

        # Auto-generate description
        if not self.description and self.label:
            self.description = self.label

        # Resolve each per-direction icon from the widest declared value it
        # inherits, so all four are set whatever the author declared. Each
        # _multi falls back to its own direction, not to icon, or a type
        # declaring icon= plus icon_out= would lose icon_out on its multi-link
        # outlets — which is every DATA outlet.
        self.icon_in = self.icon_in or self.icon
        self.icon_out = self.icon_out or self.icon
        self.icon_in_multi = self.icon_in_multi or self.icon_in
        self.icon_out_multi = self.icon_out_multi or self.icon_out
