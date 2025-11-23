
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar, Union, TYPE_CHECKING
from dataclasses import dataclass, field

from ...data.fields import DataField
from ...types.ports import DataPort
from ...registry.identity import BaseIdentity
from ...errors.haywire_exception import HaywireException

@dataclass
class WidgetIdentity(BaseIdentity):
    """Core identifying attributes of a widget"""
    _is_error: bool = False
    _error_priority: int = 0

# ============================================================================
#    BASE WIDGET CLASS
# ============================================================================

class BaseWidget(ABC):
    """Abstract base class for all widgets
    
    Args:
        element (DataPort): The data port this widget is associated with.
        error (Optional[HaywireException]): Optional error information.
    """

    def __init__(self, element: DataPort, error: Optional[HaywireException] = None):
        self.element: DataPort = element
        self.element_id: str = element.id
        self.data_field: DataField = element.data
        self.ui_properties: Dict[str, Any] = element.ui.get('properties', {}) if hasattr(element, 'ui') else {}
        self.ui_element = None
        self.error: Optional[HaywireException] = error

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

    def get_value(self) -> Any:
        """Get the current data field value"""
        return self.data_field.get_value()

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

