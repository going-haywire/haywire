from abc import ABC, abstractmethod
from collections.abc import Callable
import logging
from typing import Any, Optional
from nicegui import ui
from haywire.core.types.ports import DataPort
from haywire.ui.widget.interface import IWidget

class SimpleWidget(IWidget, ABC):
    """
    Simple, high-performance widget for basic use cases.
    
    Features:
    - Direct DataPort ↔ UI binding (no converter pipeline)
    - Automatic unwrapping of PrimitiveType
    - Two-way sync with minimal overhead
    
    Limitations:
    - Single UI element only
    - Single value binding only
    - No custom converters
    - No validation
    - No debouncing
    
    Perfect for:
    - Number inputs
    - Text inputs
    - Checkboxes
    - Sliders
    - Any simple primitive type widget
    
    Class Attributes (override if needed):
        UI_PROPERTY: Property name to bind (default: 'value')
        UI_EVENT: Event name to listen for (default: 'update:modelValue')
        IS_READONLY: Whether widget is read-only (default: False)
    
    Usage:
        @widget(compatible_types=[FLOAT])
        class FastNumberWidget(SimpleWidget):
            def create_element(self):
                return ui.number(value=0)
            
            def get_default_value(self):
                return 0.0
    """
    
    # Metadata (set by @widget decorator)
    class_identity: Any
    class_library: Any
    
    # Defaults work for most NiceGUI elements
    UI_PROPERTY: str = 'value'
    UI_EVENT: str = 'update:modelValue'
    IS_READONLY: bool = False
    
    def __init__(self, port: DataPort):
        """Initialize simple widget"""
        self.port = port
        self.port_id: str = port.id
        self.ui_properties: dict = (
            port.widget_config.get('properties', {}) 
            if hasattr(port, 'widget_config') 
            else {}
        )
        
        # UI element (created during render)
        self.ui_element: ui.element | None = None
        
        # Cleanup callbacks
        self._model_changed_callback: Optional[Callable] = None
        self._ui_changed_callback: Optional[Callable] = None
        self.logger = logging.getLogger(__name__)

    @abstractmethod
    def create_element(self) -> Any:
        """
        Create and return the NiceGUI element.
        
        The element should be created with initial value of 0 or empty.
        SimpleWidget will sync it immediately after creation.
        
        Example:
            def create_element(self):
                return ui.number(value=0, min=0, max=100)
        """
        pass
    
    def render(self) -> Any:
        """
        Render widget with automatic binding setup.
        """
        if self.ui_element is None:
            # Create UI element
            self.ui_element = self.create_element()
            
            # Setup binding
            self._setup_binding()
            
            # Initial sync: Model → View
            self._sync_to_view()
            
            # Cleanup on disconnect
            if hasattr(self.ui_element, 'client'):
                self.ui_element.client.on_disconnect(lambda: self.cleanup())
        
        return self.ui_element
    
    def _setup_binding(self) -> None:
        """
        Setup bidirectional or unidirectional binding.
        """
        # Model → View: Subscribe to data field changes
        self._model_changed_callback = lambda _: self._sync_to_view()
        self.port._data.on_changed += self._model_changed_callback
        
        # View → Model: Subscribe to UI element changes (if writable)
        if not self.IS_READONLY:
            self._ui_changed_callback = lambda e: self._sync_to_model()
            self.ui_element.on(self.UI_EVENT, self._ui_changed_callback)
    
    def _sync_to_view(self) -> None:
        """
        Synchronize DataPort → UI element.
        """
        value = self.port.get_value()
        if value is None:
            value = self.get_default_value()
        setattr(self.ui_element, self.UI_PROPERTY, value)
    
    def _sync_to_model(self) -> None:
        """
        Synchronize UI element → DataPort.
        """
        value = getattr(self.ui_element, self.UI_PROPERTY)
        self.port.set_value(value)
    
    def get_default_value(self) -> Any:
        """
        Get default value for this widget type.
        Override if your widget needs a specific default.
        
        Returns:
            Default value (e.g., 0 for numbers, '' for strings, False for bools)
        """
        return None
    
    def cleanup(self) -> None:
        """Clean up subscriptions"""
        if self._model_changed_callback:
            try:
                self.port._data.on_changed -= self._model_changed_callback
            except Exception as e:
                self.logger.warning(f"Failed to clean up model event listener: {e}", exc_info=True)
        
        if self._ui_changed_callback and not self.IS_READONLY:
            try:
                self.ui_element.delete()
            except Exception as e:
                self.logger.warning(f"Failed to clean up UI event listener: {e}", exc_info=True)
        
        self.port = None
        self.ui_element = None
