"""
UINode - Manager class for node UI lifecycle with reliable cleanup and hot reload support

This class manages the relationship between a HaywireNode and its UI representation,
using a container-slot approach for reliable re-rendering and cleanup.

Enhanced with hot reload support: UINode subscribes to NodeWrapper change callbacks
and automatically re-renders when the underlying node class is hot-reloaded.
"""

import logging
from typing import Optional, TYPE_CHECKING, List
from nicegui import ui
from haywire.core.node.base import BaseNode
from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType

from haywire.ui.ui_nodecard import UINodeCard
from haywire.ui.renderer.factory import RenderFactory

class UINode:
    """
    Manages the lifecycle and rendering of a HaywireNode's UI representation.
    
    This class:
    - Holds references to HaywireNode and NodeRenderFactory
    - Uses container-slot approach for reliable cleanup during re-rendering
    - Delegates all rendering logic to the factory
    - Has no knowledge of renderers or widgets (clean separation)
    - Subscribes to NodeWrapper for hot reload support
    """

    def __init__(
            self, 
            container: ui.element,
            wrapper: NodeWrapper,
            factory: RenderFactory
            ):
        """
        Initialize UINode with node, factory, and parent component.
        
        Args:
            wrapper: NodeWrapper for hot reload support
            component: Parent NiceGUI component to render into
            factory: NodeRenderFactory for creating UI representations
        """
        self.wrapper: NodeWrapper = wrapper
        self.haywire_node: BaseNode = wrapper.node
        self.factory: RenderFactory = factory
        self.container: ui.element = container

        self._position: Optional[tuple[int, int]] = None
        
        # Container slot for reliable cleanup
        self.container_slot: Optional[ui.column] = None
        
        # Current UI representation
        self.current_ui_card: Optional[UINodeCard] = None
        
        # Generate unique ID for this UINode
        self.ui_node_id = f"ui-node-{id(self)}"
        
        # Subscribe to wrapper changes for hot reload support
        self.wrapper.add_livecycle_subscriber(self._listen_on_wrapper_livecycle_event)
        
        # Subscribe to factory renderer changes for hot reload support
        self.factory.add_factory_lifecycle_subscriber(self.wrapper.node_id, self._listen_on_factory_lifecycle_event)
    
        self._error_renderer_reg_key: str = self.factory._renderer_registry.get_error_renderer_registry_key()
        self._default_renderer_reg_key: str = self.factory._renderer_registry.get_default_renderer_registry_key()

        self.container.client.on_disconnect(lambda: self.cleanup())

    @property
    def position(self) -> Optional[tuple[int, int]]:
        return self._position

    @position.setter
    def position(self, value: tuple[int, int]):
        self._position = value

    def set_position(self, position: tuple[int, int]):
        """
        Set the position of the UINode in the UI.
        
        Args:
            position: (x, y) tuple for node position
        """
        self.position = position

    def refresh(self) -> bool:
        """
        Refresh the current rendering of the node.
        """
        self.wrapper.recall_change(self._listen_on_wrapper_livecycle_event)

    def _listen_on_wrapper_livecycle_event(self, event: LifeCycleEvent):
        """
        Handle NodeWrapper hot reload event notifications.
        
        This is called by the NodeWrapper when hot reload events occur, including:
        - CLASS_RELOADED: Node class was hot-reloaded with new definition (migration_completed)
        - CLASS_RELOAD_FAILED: Hot reload failed (initialization or migration errors)
        - CLASS_ADDED: Initial node creation
        
        IMPORTANT: This may be called from background threads (file watcher).
        We use ui.context.client to ensure UI updates run in the correct context.
        
        Args:
            event: The hot reload event with complete context
        """
        logging.debug(f"🔄 UINode {self.haywire_node.node_id}: Wrapper event - {event.event_type.value}")
        
        # Define the UI update function that needs to run in UI context
        if event.event_type == LifeCycleEventType.CLASS_RELOADED:
            # Node class has been hot-reloaded (migration completed)
            if self.wrapper:
                self.haywire_node = self.wrapper.node
            renderer_reg_key = self.haywire_node.ui_config.node_renderer
            if renderer_reg_key is None:
                renderer_reg_key = self._default_renderer_reg_key
            logging.debug(f"✨ Hot reload: Re-rendering node {self.haywire_node.node_id} with renderer '{renderer_reg_key}'")
            self.render(renderer_reg_key, _is_error_render=False)
            
        elif event.is_warning_event():
            # Error occurred during initialization or migration
            if self.wrapper:
                self.haywire_node = self.wrapper.node  # May now be an error node
            logging.debug(f"⚠️ Node error: Re-rendering node {self.haywire_node.node_id} with error renderer '{self._error_renderer_reg_key}'")
            self.render(self._error_renderer_reg_key, _is_error_render=True)
            
        elif event.event_type == LifeCycleEventType.CLASS_ADDED:
            # Node was successfully initialized
            if self.wrapper:
                self.haywire_node = self.wrapper.node
            renderer_reg_key = self.haywire_node.ui_config.node_renderer
            if renderer_reg_key is None or renderer_reg_key == '':
                renderer_reg_key = self._default_renderer_reg_key
            logging.debug(f"✅ Node ready: {self.haywire_node.node_id}")
            self.render(renderer_reg_key, _is_error_render=False)
        
    
    def _listen_on_factory_lifecycle_event(self, node_id: str) -> None:
        """
        Handle renderer hot reload notifications from NodeRenderFactory.
        
        This is called when either
        - a renderer class is reloaded, added, or removed.
        - a widget class is reloaded, added, or removed.
        We check if it's the renderer we're currently using and re-render if so.
                
        Args:
            node_id: The ID of the node whose renderer has changed
        """
        # this is a safty check, normally the factory should only notify relevant nodes
        if self.wrapper.node_id == node_id:
            self.render()

    def render(self, renderer_name: str | None = None, _is_error_render: bool = False) -> bool:            
        # Run UI updates in the proper context (same as wrapper changes)
        if self.container_slot and hasattr(self.container_slot, 'client'):
            with self.container_slot.client:
                if self._render(renderer_name, _is_error_render=_is_error_render):
                    ui.notify(f"Node {self.haywire_node.node_id} hot-reloaded", type='positive')
                else:
                    ui.notify(f"Error rendering node {self.haywire_node.node_id}", type='negative')
        else:
            return self._render(renderer_name, _is_error_render=_is_error_render)

    def _render(self, renderer_name: str | None = None, _is_error_render: bool = False) -> bool:
        """
        Render the node using the specified renderer.
        
        Args:
            renderer_name: Name of the renderer/renderer to use (None for default)
        """
        with self.container:
            try:
                # Clean up old widgets before clearing UI
                if self.current_ui_card:
                    self.current_ui_card.cleanup()            # Create or clear the container slot
                if self.container_slot:
                    self.container_slot.clear()  # NiceGUI handles cleanup reliably
                else:
                    self.container_slot = ui.column().classes('ui-node-slot').props(f'id="{self.ui_node_id}"')
                
                # Render into the container slot
                with self.container_slot:
                    if renderer_name is None:
                        renderer_name = self.haywire_node.ui_config.node_renderer

                    if renderer_name is None:
                        renderer_name = self.factory._renderer_registry.get_default_renderer_registry_key()

                    self.current_ui_card = self.factory.render(renderer_name, self.wrapper, _is_error_render=_is_error_render)

                    return True  # Render successful
            except Exception as e:
                # Clean up old widgets before clearing UI
                if self.current_ui_card:
                    self.current_ui_card.cleanup()            # Create or clear the container slot
                if self.container_slot:
                    self.container_slot.clear()  # NiceGUI handles cleanup reliably

                self.container_slot = None

                error = HaywireException.from_exception(
                    exception=e,
                    message=f"FATAL Error rendering node: {e}",
                    category="FATAL Rendering Error",
                    operation="UINode.render",
                ).enrich(
                    registry_key=renderer_name
                ).log()

                return False    

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
        
    def delete(self):
        """
        Delete the UINode and clean up resources.
        """
        # Unregister from factory tracking
        self.factory._unregister_node(self.wrapper.node_id)
        # Clean up this session resources
        self.cleanup()

    def cleanup(self):
        """
        Clean up resources and remove UI elements.
        Enhanced to unsubscribe from wrapper and factory callbacks.
        """
        logging.info(f"🔌 Cleaning up UINode {self.haywire_node.node_id} ..")
        self.factory.remove_factory_lifecycle_subscriber(self.wrapper.node_id, self._listen_on_factory_lifecycle_event)

        # Unsubscribe from wrapper changes
        if self.wrapper:
            try:
                self.wrapper.remove_livecycle_subscriber(self._listen_on_wrapper_livecycle_event)
            except Exception as e:
                logging.info(f"⚠️ Error unsubscribing from wrapper: {e}")
            self.wrapper = None
            self.haywire_node = None
        
        # Clean up widgets before clearing UI
        if self.current_ui_card:
            self.current_ui_card.cleanup()
        
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
        logging.info(f".. Done 🔌 Cleaning up UINode.")
    
    def is_rendered(self) -> bool:
        """Check if the node is currently rendered."""
        return self.current_ui_card is not None and self.container_slot is not None
    
    def get_node_data(self) -> BaseNode:
        """Get the underlying HaywireNode data."""
        return self.haywire_node
    
    def get_ui_node_id(self) -> str:
        """Get the unique UI node ID."""
        return self.ui_node_id
