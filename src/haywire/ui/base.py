"""
Base widget classes for the Haywire widget system
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from nicegui import ui, element

from haywire.core.node.node import HaywireNode, NodeErrorInfo
from haywire.core.registry.registry import WidgetRegistry

from haywire.core.data.fields import DataField
from haywire.core.node.elements import ConfigurableElement


class UINodeCard:
    """
    Container for a rendered node's UI elements and widget instances.
    
    Holds the NiceGUI card element and mappings to all widget instances
    for easy access and management.
    """
    
    def __init__(self, ui_card, ui_elements: Dict[str, Any], widget_instances: Dict[str, Any]):
        """
        Initialize UINodeCard with UI elements.
        
        Args:
            ui_card: The main NiceGUI card element
            ui_elements: Mapping of element IDs to UI elements
            widget_instances: Mapping of element IDs to widget instances
        """
        self.ui_card = ui_card
        self.ui_elements = ui_elements
        self.widget_instances = widget_instances
    
    def get_widget_instance(self, element_id: str) -> Optional[Any]:
        """Get a widget instance by element ID."""
        return self.widget_instances.get(element_id)
    
    def get_ui_element(self, element_id: str) -> Optional[Any]:
        """Get a UI element by element ID."""
        return self.ui_elements.get(element_id)
    
    def update_element_value(self, element_id: str, new_value: Any) -> bool:
        """
        Update an element's value through its widget.
        
        Args:
            element_id: ID of the element to update
            new_value: New value to set
            
        Returns:
            True if update was successful, False otherwise
        """
        widget_instance = self.widget_instances.get(element_id)
        if widget_instance and hasattr(widget_instance, 'update_value'):
            try:
                widget_instance.update_value(new_value)
                return True
            except Exception as e:
                print(f"Failed to update element {element_id}: {e}")
                return False
        return False


class BaseWidget(ABC):
    """Abstract base class for all widgets"""
    
    def __init__(self, element: ConfigurableElement):
        self.element: ConfigurableElement = element 
        self.element_id: str = element.id
        self.data_field: DataField = element.data
        self.ui_properties: Dict[str, Any] = element.ui.get('properties', {}) if hasattr(element, 'ui') else {}
        self.ui_element = None
    
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
    
    def render(self) -> Any:
        """Render the widget and return the UI element"""
        if self.ui_element is None:
            self.ui_element = self.create_element()
        return self.ui_element


class BaseNodeRenderer(ABC):
    """
    Abstract base class for all NodeRenderer classes.
    
    NodeRenderer classes are stateless and define the look and structure of nodes.
    They are cached and reused by the NodeRenderFactory.
    """
    
    def __init__(self, widget_registry: WidgetRegistry):
        """
        Initialize the renderer with a widget registry.
        
        Args:
            widget_registry: Registry for resolving widget classes
        """
        self.widget_registry = widget_registry
    
    @abstractmethod
    def render(self, node: HaywireNode) -> UINodeCard:
        """
        Render a node into a UINodeCard.
        
        Args:
            node: The HaywireNode to render
            
        Returns:
            UINodeCard containing the rendered UI and widget instances
        """
        pass

    def _render_error_info(self, error_info: NodeErrorInfo) -> element:
        """
        Render error information for a node.

        Args:
            node: The HaywireNode with error information
            
        Returns:
            bool: True if error info was rendered, False if no error info
        """
        with ui.column().classes('items-left p-2 border border-red-500 bg-red-50') as error_column:
            with ui.row():
                ui.icon('error', color='red').classes('text-lg')
                ui.label(error_info.error).classes('text-lg text-red-600')
            ui.label(error_info.error_message).classes('text-sm text-red-600')
            if error_info.note:
                for value in error_info.note:
                    ui.label(value).classes('text-sm text-red-600')
            ui.label(error_info.timestamp).classes('text-sm text-red-600')
        return error_column
