"""
Gadgets Registry - Registry system for NodeRenderer classes

This registry manages NodeRenderer classes using the same pattern as the widget registry,
with fallback support for default and error renderers.
"""

from typing import Dict, Type, Optional, Any
from abc import ABC, abstractmethod
from haywire.core.registry.base import BaseRegistry
from haywire.core.node.node import NodeData
from haywire.core.registry.registry import WidgetRegistry


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
    def render(self, node: NodeData) -> UINodeCard:
        """
        Render a node into a UINodeCard.
        
        Args:
            node: The HaywireNode to render
            
        Returns:
            UINodeCard containing the rendered UI and widget instances
        """
        pass


class GadgetsRegistry(BaseRegistry):
    """Registry for NodeRenderer classes with fallback support"""
    
    def __init__(self):
        super().__init__()
        self._default_renderer: str | None = None
        self._error_renderer: str | None = None
    
    def register_default_renderer(self, renderer_name: str):
        """Register the default renderer name"""
        self._default_renderer = renderer_name
    
    def register_error_renderer(self, renderer_name: str):
        """Register the error renderer name"""
        self._error_renderer = renderer_name
    
    def get_renderer_class(self, renderer_name: str | None) -> Type[BaseNodeRenderer]:
        """
        Get renderer class with fallback strategy:
        1. Use default if no renderer name is specified
        2. Try exact renderer name lookup
        3. Return error renderer if exact renderer doesn't exist
        """
        # 1. Use default if no renderer name is specified
        if renderer_name is None:
            if self._default_renderer and self.has(self._default_renderer):
                return self.get(self._default_renderer)
        else:
            # 2. Try exact renderer name lookup
            if self.has(renderer_name):
                return self.get(renderer_name)
        
        # 3. Return error renderer if exact renderer doesn't exist
        if self._error_renderer and self.has(self._error_renderer):
            return self.get(self._error_renderer)
        
        # Fallback if no error renderer registered
        raise RuntimeError(f"No renderer found for '{renderer_name}' and no error renderer registered")
    
    def register_renderer(self, name: str, renderer_class: Type[BaseNodeRenderer], metadata: Optional[Dict[str, Any]] = None):
        """
        Register a renderer class.
        
        Args:
            name: Unique name for the renderer
            renderer_class: The NodeRenderer class
            metadata: Optional metadata for the renderer
        """
        self.register(name, renderer_class, metadata)
