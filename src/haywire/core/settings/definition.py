# haywire/core/settings/definition.py
"""
SettingDefinition - schema for a setting.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

from .enums import SettingScope

T = TypeVar('T')


@dataclass
class SettingDefinition(Generic[T]):
    """
    Schema for a single setting.
    
    Defines the type, default value, validation rules, and UI metadata.
    Used by both GlobalSettingsRegistry (for global definitions) and
    SettingsHolder (for local-only definitions).
    """
    name: str
    """Unique identifier, use dot notation for hierarchy: 'ui.node.bg_color'"""
    
    default: T
    """Default value when mode is AUTO"""
    
    type_: type
    """Python type for validation and UI generation"""
    
    scope: SettingScope = SettingScope.GLOBAL_AWARE
    """Whether this setting participates in global resolution"""
    
    # UI metadata
    label: str | None = None
    """Human-readable label for UI"""
    
    description: str = ""
    """Help text / tooltip"""
    
    category: str = "general"
    """Category for grouping in settings UI"""
    
    # Validation
    validator: Callable[[T], bool] | None = None
    """Custom validation function"""
    
    choices: list[T] | None = None
    """Valid choices (for dropdown/enum settings)"""
    
    min_value: T | None = None
    """Minimum value (for numeric settings)"""
    
    max_value: T | None = None
    """Maximum value (for numeric settings)"""
    
    # UI hints
    ui_widget: str | None = None
    """Preferred widget type: 'color', 'slider', 'dropdown', 'text', etc."""
    
    ui_order: int = 0
    """Display order within category"""
    
    def __post_init__(self):
        if self.label is None:
            # 'ui.node.bg_color' → 'Bg Color'
            self.label = self.name.split('.')[-1].replace('_', ' ').title()
    
    def validate(self, value: T) -> bool:
        """
        Validate a value against this definition.
        
        Returns True if valid, False otherwise.
        """
        # Type check (lenient - allow compatible types)
        if value is not None:
            if self.type_ == float and isinstance(value, int):
                pass  # int is valid for float
            elif self.type_ == str and not isinstance(value, str):
                return False
            elif self.type_ == bool and not isinstance(value, bool):
                return False
            elif self.type_ == int and not isinstance(value, int):
                return False
        
        # Choices validation
        if self.choices is not None and value not in self.choices:
            return False
        
        # Range validation
        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False
        
        # Custom validator
        if self.validator is not None:
            try:
                if not self.validator(value):
                    return False
            except Exception:
                return False
        
        return True
    
    def coerce(self, value: Any) -> T:
        """
        Attempt to coerce a value to the correct type.
        
        Raises ValueError if coercion fails.
        """
        if value is None:
            return self.default
        
        if isinstance(value, self.type_):
            return value
        
        try:
            if self.type_ == bool:
                if isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                return bool(value)
            elif self.type_ == int:
                return int(value)
            elif self.type_ == float:
                return float(value)
            elif self.type_ == str:
                return str(value)
            else:
                return self.type_(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Cannot coerce {value!r} to {self.type_.__name__}: {e}")
    
    def to_dict(self) -> dict:
        """Serialize definition (for TOML-defined settings)."""
        return {
            'default': self.default,
            'type': self.type_.__name__,
            'scope': self.scope.name,
            'label': self.label,
            'description': self.description,
            'category': self.category,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'choices': self.choices,
            'ui_widget': self.ui_widget,
            'ui_order': self.ui_order,
        }