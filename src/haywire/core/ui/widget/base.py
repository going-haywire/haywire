
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Set, Type, TypeVar, Union, TYPE_CHECKING
from dataclasses import dataclass, field

from haywire.core.library.identity import LibraryIdentity

from ...types.interface import IType
from ...data.fields import DataField
from ...types.ports import DataPort
from ...registry.identity import BaseIdentity

@dataclass
class WidgetIdentity(BaseIdentity):
    """Core identifying attributes of a widget"""
    compatible_types: Set[Type[IType]] = field(default_factory=set)

# ============================================================================
#    BASE WIDGET CLASS
# ============================================================================

class BaseWidget(ABC):
    """Abstract base class for all widgets
    
    Args:
        element (DataPort): The data port this widget is associated with.
    """

    class_identity: WidgetIdentity
    class_library: LibraryIdentity

    def __init__(self, element: DataPort):
        self.element: DataPort = element
        self.element_id: str = element.id
        self.data_field: DataField = element.data
        self.ui_properties: Dict[str, Any] = element.ui.get('properties', {}) if hasattr(element, 'ui') else {}
        self.ui_element = None

        # Add change handler for the data field
        self.data_field.on_changed += self._call_on_model_changed

    def _call_on_model_changed(self, new_value: Any):
        """Handle data field changes by updating the UI"""
        if self.ui_element is not None and new_value is not None:
            self.on_value_change(new_value)

    @abstractmethod
    def on_value_change(self, value: Any):
        """Update the UI element with a new value"""
        pass

    @abstractmethod
    def create_element(self) -> Any:
        """Create and return the NiceGUI element"""
        pass

    def update_value(self, new_value: Any):
        """Update the data field value"""
        self.data_field.set_value(new_value)

    def _update_typed_value(self, new_value: Any):
        """Update the data field value"""
        self.data_field.set_inner_value(new_value)

    def get_value(self) -> Any:
        """Get the current data field value"""
        return self.data_field.get_value()

    def _get_typed_value(self) -> Any:
        """
        Get value from data field, unwrapping if necessary.
        """
        raw_value = self.get_value()
        
        # Handle pooled fields (returns dict)
        if isinstance(raw_value, dict):
            return self._handle_pooled_value(raw_value)
        
        # Unwrap PrimitiveType instances
        if hasattr(raw_value, 'value'):
            return raw_value.value
        
        return raw_value
    
    def _handle_pooled_value(self, pooled_dict: dict) -> Any:
        """Handle pooled field values."""
        if not pooled_dict:
            return None
        values = list(pooled_dict.values())
        first = values[0]
        return first.value if hasattr(first, 'value') else first

    def on_ui_change(self, e):
        self.update_value(e.sender.value)

    def render(self) -> Any:
        """Render the widget and return the UI element"""
        if self.ui_element is None:
            self.ui_element = self.create_element()
            self.ui_element.on('update:modelValue', self.on_ui_change)
            self.ui_element.client.on_disconnect(lambda: self.cleanup())
        return self.ui_element

    def cleanup(self):
        print(f"Cleaning up widget: {self.class_identity.registry_key} for element ID: {self.element_id}")
        self.element = None
        self.element_id = None

        """Clean up event handlers"""
        self.data_field.on_changed -= self._call_on_model_changed

        self.data_field = None

