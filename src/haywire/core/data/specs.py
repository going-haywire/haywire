from __future__ import annotations
from typing import Any
from dataclasses import dataclass, field, replace

from haywire.core.data.fields import SingleField, PooledField, DataField

from .enums import DataType, DataContainerType

@dataclass
class DataFieldSpec:
    """Defines the specification for a data field.

    Provides metadata about a field's type, container, default value, and UI hints.
    This is a flexible class where only 'type' is strictly required.

    Attributes:
        type: The fundamental data type (e.g., INT, FLOAT).
        container: The data structure container (e.g., SCALAR, LIST).
        value: The default value for the field.
        is_pooled: Whether the field accepts multiple input sources.
        id: Unique identifier, auto-generated if not provided.
        label: Human-readable label, auto-generated if not provided.
        description: Detailed description, auto-generated if not provided.
        widget: Suggested UI widget, auto-generated if not provided.
        ui: Dictionary for extra UI-specific configurations.
    """
    type: DataType
    container: DataContainerType = DataContainerType.SINGLE
    value: Any = None
    id: str | None = None
    label: str | None = None
    description: str | None = None
    widget: str | None = None
    ui: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate default values for optional fields after initialization."""
        # Generate a unique ID if not provided, e.g., "INT_SCALAR"
        if self.id is None:
            self.id = f"{self.type.value.upper()}_{self.container.value.upper()}"

        # Generate a human-readable label if not provided, e.g., "Int:Scalar"
        if self.label is None:
            self.label = f"{self.type.value.capitalize()}:{self.container.value.capitalize()}"

        # Ensure description is a string
        if self.description is None:
            self.description = ""

        # Set a default value if none is provided, based on type and container
        if self.value is None:
            if self.container == DataContainerType.SINGLE:
                if self.type == DataType.FLOAT:
                    self.value = 0.0
                elif self.type == DataType.INT:
                    self.value = 0
                elif self.type == DataType.BOOL:
                    self.value = False
                elif self.type == DataType.STRING:
                    self.value = ""
                else:
                    self.value = None  # Default for OBJECT, etc.
            elif self.container in [DataContainerType.LIST, DataContainerType.SET]:
                self.value = []
            elif self.container == DataContainerType.DICT:
                self.value = {}


    def create_field(self, is_pooled: bool = False) -> DataField:
        """Create appropriate DataField instance based on pooled flag"""
        if is_pooled:
            return PooledField(
                type=self.type,
                value={},
                is_pooled=True
            )
        else:
            return SingleField(
                type=self.type,
                value=self.value,
                is_pooled=False
            )

    def __call__(self, **kwargs: Any) -> DataFieldSpec:
        """Create a new instance with overridden attributes."""
        return replace(self, **kwargs)


def specs_factory(**kwargs: Any) -> DataFieldSpec:
    """Factory function to create a DataFieldSpec instance.

    This allows creating a template spec and then calling it to produce
    configured instances.

    Example:
        INT = specs_factory(type=DataType.INT)
        my_int_field = INT(value=10)
    """
    return DataFieldSpec(**kwargs)
