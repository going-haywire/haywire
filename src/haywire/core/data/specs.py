from __future__ import annotations
from typing import Any, Callable
from dataclasses import dataclass, field

from .enums import DataType, DataCategory
from .fields import DataField, SingleField, PooledField


@dataclass
class DataFieldSpec:
    """Factory specification for creating DataField instances
    
    Attributes:
        type: Data type (INT, FLOAT, STRING, etc.)
        category: Data category (SCALAR, LIST, SET, DICT)
        value: Default value for the field
        is_pooled: Whether field accepts multiple input sources
        id: Unique identifier for the field specification
        label: Human-readable label displayed in UI
        description: Detailed description of the field's purpose
        widget: UI widget type (e.g., 'slider', 'input', 'select')
        ui: Dictionary for UI-specific configurations
    """
    type: DataType = DataType.STRING
    category: DataCategory = DataCategory.SCALAR
    value: Any = None
    is_pooled: bool = False
    id: str | None = field(default=None, init=False, repr=False)
    label: str | None = field(default=None, init=False, repr=False)
    description: str | None = field(default=None, init=False, repr=False)   
    widget: str | None = field(default=None, init=False, repr=False)
    ui: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        if self.id is None:
            self.id = self.type.value.upper() + '_' + self.category.value.upper()
        if self.label is None:
            self.label = self.type.value.capitalize() + ':' + self.category.value.capitalize()
        if self.description is None:
            self.description = ""
        if self.value is None:
            if not self.is_pooled:
                if self.category == DataCategory.SCALAR:
                    if self.type == DataType.FLOAT:
                        self.value = 0.0
                    elif self.type == DataType.INT:
                        self.value = 0
                    elif self.type == DataType.BOOL:
                        self.value = False
                    elif self.type == DataType.STRING:
                        self.value = ""
                    elif self.type == DataType.LIST:
                        self.value = []
                    elif self.type == DataType.DICT:
                        self.value = {}
            else:
                self.value = {}
            
    def create_field(self, no_pooling: bool = False) -> DataField:
        """Create appropriate DataField instance based on pooled flag"""
        if no_pooling or not self.is_pooled:
            return SingleField(
                id=self.id,
                type=self.type,
                category=self.category,
                value=self.value,
                is_pooled=False
            )
        else:
            return PooledField(
                id=self.id,
                type=self.type,
                category=self.category,
                value={},
                is_pooled=True
            )


def specs_factory(data_type: DataType, category: DataCategory = DataCategory.SCALAR, **default_kwargs) -> Callable[..., DataFieldSpec]:
    """
    Create a factory function for generating DataFieldSpec instances.
    
    Example:
        INT = specs_factory(DataType.INT, DataCategory.SCALAR)
        my_int_spec = INT(value=10, widget='slider')
    """
    def factory_func(**kwargs) -> DataFieldSpec:
        merged_kwargs = {**default_kwargs, **kwargs}
        return DataFieldSpec(type=data_type, category=category, **merged_kwargs)
    return factory_func
