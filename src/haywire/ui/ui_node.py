"""
UINode - Manager class for node UI lifecycle with reliable cleanup

This class manages the relationship between a HaywireNode and its UI representation,
using a container-slot approach for reliable re-rendering and cleanup.
"""

from typing import Optional
from nicegui import ui
from haywire.core.node.node import BaseNode
from haywire.core.ui.base import UINodeCard
from haywire.ui.node_render_factory import NodeRenderFactory


class UINode:
    """
    Manages the lifecycle and rendering of a HaywireNode's UI representation.
    
    This class:
    - Holds references to HaywireNode and NodeRenderFactory
    - Uses container-slot approach for reliable cleanup during re-rendering
    - Delegates all rendering logic to the factory
    - Has no knowledge of renderers or widgets (clean separation)
    """

    def __init__(self, haywire_node: BaseNode, factory: NodeRenderFactory, component):
        """
        Initialize UINode with node, factory, and parent component.
        
        Args:
            haywire_node: The HaywireNode data model
            factory: NodeRenderFactory for creating UI representations
            component: Parent NiceGUI component to render into
        """
        self.haywire_node = haywire_node
        self.factory = factory
        self.component = component
        
        # Container slot for reliable cleanup
        self.container_slot: Optional[ui.column] = None
        
        # Current UI representation
        self.current_ui_card: Optional[UINodeCard] = None
        
        # Generate unique ID for this UINode
        self.ui_node_id = f"ui-node-{id(self)}"
    
    def render(self, renderer_name: str | None = None):
        """
        Render the node using the specified renderer.
        
        Args:
            renderer_name: Name of the renderer/renderer to use (None for default)
        """
        with self.component:
            # Create or clear the container slot
            if self.container_slot:
                self.container_slot.clear()  # NiceGUI handles cleanup reliably
            else:
                self.container_slot = ui.column().classes('ui-node-slot').props(f'id="{self.ui_node_id}"')
            
            # Render into the container slot
            with self.container_slot:
                if renderer_name is None:
                    renderer_name = self.haywire_node.renderer
                self.current_ui_card = self.factory.generate_node(renderer_name, self.haywire_node)
    
    def rerender(self, renderer_name: str | None = None):
        """
        Re-render the node with reliable cleanup.
        
        Args:
            renderer_name: Name of the renderer/renderer to use (None for default)
        """
        # Reliable cleanup via container slot
        if self.container_slot:
            self.container_slot.clear()  # NiceGUI handles the cleanup
        
        # Re-render
        self.render(renderer_name)
    
    def get_widget_instance(self, element_id: str):
        """
        Get a widget instance by element ID.
        
        Args:
            element_id: ID of the widget element
            
        Returns:
            Widget instance or None if not found
        """
        if self.current_ui_card:
            return self.current_ui_card.get_widget_instance(element_id)
        return None
    
    def get_ui_element(self, element_id: str):
        """
        Get a UI element by element ID.
        
        Args:
            element_id: ID of the UI element
            
        Returns:
            UI element or None if not found
        """
        if self.current_ui_card:
            return self.current_ui_card.get_ui_element(element_id)
        return None
    
    def update_element_value(self, element_id: str, new_value) -> bool:
        """
        Update an element's value through its widget.
        
        Args:
            element_id: ID of the element to update
            new_value: New value to set
            
        Returns:
            True if update was successful, False otherwise
        """
        if self.current_ui_card:
            return self.current_ui_card.update_element_value(element_id, new_value)
        return False
    
    def destroy(self):
        """
        Clean up resources and remove UI elements.
        """
        # Clear the container slot (reliable cleanup)
        if self.container_slot:
            try:
                self.container_slot.clear()
                # Optionally remove the container itself
                self.container_slot.delete()
            except:
                pass  # Element might already be deleted
            self.container_slot = None
        
        # Clear references
        self.current_ui_card = None
    
    def is_rendered(self) -> bool:
        """Check if the node is currently rendered."""
        return self.current_ui_card is not None and self.container_slot is not None
    
    def get_node_data(self) -> BaseNode:
        """Get the underlying HaywireNode data."""
        return self.haywire_node
    
    def get_ui_node_id(self) -> str:
        """Get the unique UI node ID."""
        return self.ui_node_id
