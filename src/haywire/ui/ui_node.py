"""
UINode - Manager class for node UI lifecycle with reliable cleanup and hot reload support

This class manages the relationship between a HaywireNode and its UI representation,
using a container-slot approach for reliable re-rendering and cleanup.

Enhanced with hot reload support: UINode subscribes to NodeWrapper change callbacks
and automatically re-renders when the underlying node class is hot-reloaded.
"""

from typing import Optional, TYPE_CHECKING, List
from nicegui import ui
from haywire.core.node.base import BaseNode
from haywire.ui.ui_nodecard import UINodeCard
from haywire.core.registry.lifecycle_event import LifeCycleEvent, LifeCycleEventType
from haywire.ui.renderer.factory import RenderFactory
from haywire.core.errors.haywire_exception import ErrorSeverity, HaywireException

if TYPE_CHECKING:
    from haywire.core.node.node_wrapper import NodeWrapper

class NiceUINode:
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
            self, haywire_node: BaseNode, 
            factory: RenderFactory, 
            component, 
            node_wrapper: 'NodeWrapper'):
        """
        Initialize UINode with node, factory, and parent component.
        
        Args:
            haywire_node: The HaywireNode data model
            factory: NodeRenderFactory for creating UI representations
            component: Parent NiceGUI component to render into
            node_wrapper: Optional NodeWrapper for hot reload support
        """
        self.haywire_node = haywire_node
        self.factory = factory
        self.component = component
        self.node_wrapper = node_wrapper
        
        # Container slot for reliable cleanup
        self.container_slot: Optional[ui.column] = None
        
        # Current UI representation
        self.current_ui_card: Optional[UINodeCard] = None
        
        # Generate unique ID for this UINode
        self.ui_node_id = f"ui-node-{id(self)}"
        
        # Subscribe to wrapper changes for hot reload support
        self.node_wrapper.add_livecycle_subscriber(self._listen_on_wrapper_livecycle_event)
        
        # Subscribe to factory renderer changes for hot reload support
        self.factory.add_renderer_lifecycle_subscriber(self._listen_on_render_lifecycle_event)
    
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
        print(f"🔄 UINode {self.haywire_node.node_id}: Wrapper event - {event.event_type.value}")
        
        # Define the UI update function that needs to run in UI context
        def update_ui():
            try:
                if event.event_type == LifeCycleEventType.CLASS_RELOADED:
                    # Node class has been hot-reloaded (migration completed)
                    if self.node_wrapper:
                        self.haywire_node = self.node_wrapper.node
                    print(f"✨ Hot reload: Re-rendering node {self.haywire_node.node_id}")
                    self.rerender()
                    ui.notify(f"Node {self.haywire_node.node_id} hot-reloaded", type='positive')
                    
                elif event.is_warning_event():
                    # Error occurred during initialization or migration
                    if self.node_wrapper:
                        self.haywire_node = self.node_wrapper.node  # May now be an error node
                    print(f"⚠️ Node error: Re-rendering node {self.haywire_node.node_id} with error state")
                    self.rerender()
                    error_msg = event.error.message if event.error else "Unknown error"
                    ui.notify(f"Error in node {self.haywire_node.node_id}: {error_msg}", type='warning')
                    
                elif event.event_type == LifeCycleEventType.CLASS_ADDED:
                    # Node was successfully initialized
                    if self.node_wrapper:
                        self.haywire_node = self.node_wrapper.node
                    print(f"✅ Node ready: {self.haywire_node.node_id}")
                    # Re-render to ensure UI is in sync
                    self.rerender()
            except Exception as e:
                print(f"❌ Error updating UI for node {self.haywire_node.node_id}: {e}")
        
        # Run UI updates in the proper context
        # NiceGUI handles thread-safety internally when using context manager
        try:
            # Try to get the client context from the container
            if self.container_slot and hasattr(self.container_slot, 'client'):
                # Run in the client's context to ensure thread-safety
                with self.container_slot.client:
                    update_ui()
            else:
                # Fallback: just call directly (may work if we're already in UI thread)
                update_ui()
        except Exception as e:
            print(f"❌ Error in wrapper change handler: {e}")
    
    def _listen_on_render_lifecycle_event(self) -> None:
        """
        Handle renderer hot reload notifications from NodeRenderFactory.
        
        This is called when a renderer class is reloaded, added, or removed.
        We check if it's the renderer we're currently using and re-render if so.
        
        IMPORTANT: Like wrapper callbacks, this may be called from background threads.
        
        Args:
            event: The hot reload event with complete context
        """
       
        # Re-render using the same thread-safe pattern as wrapper changes
        def update_ui():
            try:
                print(f"✨ Hot reload: Re-rendering node {self.haywire_node.node_id} with new renderer")
                self.rerender()
                ui.notify(f"Renderer for node {self.haywire_node.node_id} hot-reloaded", type='positive')
            except Exception as e:
                print(f"❌ Error updating UI after renderer reload: {e}")
        
        # Run UI updates in the proper context (same as wrapper changes)
        try:
            if self.container_slot and hasattr(self.container_slot, 'client'):
                with self.container_slot.client:
                    update_ui()
            else:
                update_ui()
        except Exception as e:
            print(f"❌ Error in renderer change handler: {e}")
    
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
            
            try:
                # Render into the container slot
                with self.container_slot:
                    if renderer_name is None:
                        renderer_name = self.haywire_node.ui_config.node_renderer
                    
                    self.current_ui_card = self.factory.generate_node(renderer_name, self.node_wrapper)

                    return True  # Render successful

            except Exception as e:
                if self.container_slot:
                    self.container_slot.clear()  # NiceGUI handles cleanup reliably
                else:
                    self.container_slot = ui.column().classes('ui-node-slot').props(f'id="{self.ui_node_id}"')

                error = HaywireException.from_exception(
                    exception=e,
                    message=f"Error rendering node: {e}",
                    category="Rendering Error",
                    operation="UINode.render",
                ).enrich(
                    registry_key=renderer_name
                ).log()
        
        return False  # Render failed
    
    def rerender(self, renderer_name: str | None = None):
        """
        Re-render the node with reliable cleanup.
        
        Args:
            renderer_name: Name of the renderer/renderer to use (None for default)
        """
        # Clean up old widgets before clearing UI
        if self.current_ui_card:
            self.current_ui_card.cleanup()
        
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
        
    def destroy(self):
        """
        Clean up resources and remove UI elements.
        Enhanced to unsubscribe from wrapper and factory callbacks.
        """
        # Unsubscribe from wrapper changes
        if self.node_wrapper:
            try:
                self.node_wrapper.remove_livecycle_subscriber(self._listen_on_wrapper_livecycle_event)
                print(f"🔌 Unsubscribed UINode {self.haywire_node.node_id} from wrapper callbacks")
            except Exception as e:
                print(f"⚠️ Error unsubscribing from wrapper: {e}")
            self.node_wrapper = None

        self.factory.unregister_node(self.haywire_node.node_id)

        # Unsubscribe from factory renderer changes
        try:
            self.factory.remove_renderer_lifecycle_subscriber(self._listen_on_render_lifecycle_event)
            print(f"🔌 Unsubscribed UINode {self.haywire_node.node_id} from factory callbacks")
        except Exception as e:
            print(f"⚠️ Error unsubscribing from factory: {e}")
        
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
    
    def is_rendered(self) -> bool:
        """Check if the node is currently rendered."""
        return self.current_ui_card is not None and self.container_slot is not None
    
    def get_node_data(self) -> BaseNode:
        """Get the underlying HaywireNode data."""
        return self.haywire_node
    
    def get_ui_node_id(self) -> str:
        """Get the unique UI node ID."""
        return self.ui_node_id
