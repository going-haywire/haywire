from __future__ import annotations
from typing import Any
from dataclasses import dataclass, field, replace

from haywire.core.data.fields import SingleField, PooledField, DataField

from .enums import DataType, DataContainerType

@dataclass
class DataPortSpec:
    """Defines the specification for a data field.

    Unified specification for both built-in and custom data types.
    Provides metadata about type, UI presentation, default values, and structure hints.

    Attributes:
        key: Registry key identifier (e.g., 'core:float', 'mylib:mesh_data')
        data_type: The fundamental data type (backwards compatible, can be DataType enum or string)
        label: Human-readable label
        description: Detailed description
        color: Pin color in graph UI (hex format)
        icon: Pin icon/shape name
        widget: Suggested UI widget for editing
        container: The data structure container (e.g., SINGLE, LIST)
        value: The default value for the field
        ui: Dictionary for extra UI-specific configurations
    """
    key: str
    data_type: DataType
    data_container: DataContainerType = DataContainerType.SINGLE
    id: str = ''
    label: str = ''
    description: str = ''
    color: str = '#757575'  # Default gray
    icon: str = 'circle'
    widget: str | None = None
    value: Any = None
    ui: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate default values for optional fields after initialization."""
        # Auto-generate label from key if not provided
        if not self.id:
            self.id = self.key.split(':')[-1]

        # Auto-generate label from id if not provided
        if not self.label:
            self.label = self.id.replace('_', ' ').title()
                
        # Ensure description is a string
        if not self.description:
            self.description = ""
        
        # Populate ui dict with color/icon for backward compatibility
        self.ui.setdefault('color', self.color)
        self.ui.setdefault('icon', self.icon)
        
        # Set smart defaults for value based on type and container
        if self.value is None:
            if self.data_container == DataContainerType.SINGLE:
                if self.data_type == DataType.FLOAT or (isinstance(self.data_type, str) and self.data_type == 'float'):
                    self.value = 0.0
                elif self.data_type == DataType.INT or (isinstance(self.data_type, str) and self.data_type == 'int'):
                    self.value = 0
                elif self.data_type == DataType.BOOL or (isinstance(self.data_type, str) and self.data_type == 'bool'):
                    self.value = False
                elif self.data_type == DataType.STRING or (isinstance(self.data_type, str) and self.data_type == 'str'):
                    self.value = ""
                else:
                    self.value = None  # Default for CUSTOM, etc.
            elif self.data_container in [DataContainerType.LIST, DataContainerType.SET]:
                self.value = []
            elif self.data_container == DataContainerType.DICT:
                self.value = {}


    def __call__(self, **kwargs: Any) -> DataPortSpec:
        """Create a new instance with overridden attributes."""
        return replace(self, **kwargs)


class DataFieldFactory:
    """Separate factory concerns"""
    @staticmethod
    def create(spec: DataPortSpec, is_pooled: bool = False) -> DataField:
        """Create appropriate DataField instance based on pooled flag"""
        if is_pooled:
            return PooledField(
                type=spec.data_type,
                value={},
                is_pooled=True
            )
        else:
            return SingleField(
                type=spec.data_type,
                value=spec.value,
                is_pooled=False
            )


def specs_factory(**kwargs: Any) -> DataPortSpec:
    """Factory function to create a DataFieldSpec instance.

    This allows creating a template spec and then calling it to produce
    configured instances.

    Example:
        INT = specs_factory(type=DataType.INT)
        my_int_field = INT(value=10)
    """
    return DataPortSpec(**kwargs)
