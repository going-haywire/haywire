from __future__ import annotations
from typing import Any, Type
from dataclasses import dataclass, field, replace

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


    def __call__(self, **kwargs: Any) -> DataPortSpec:
        """Create a new instance with overridden attributes."""
        return replace(self, **kwargs)
    

