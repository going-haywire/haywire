"""
UINode - Manager class for node UI lifecycle with reliable cleanup and hot reload support

This class manages the relationship between a HaywireNode and its UI representation,
using a container-slot approach for reliable re-rendering and cleanup.

Enhanced with hot reload support: UINode subscribes to NodeWrapper change callbacks
and automatically re-renders when the underlying node class is hot-reloaded.
"""

import logging
from typing import Any, Callable, Optional
from nicegui import ui
from haywire.core.graph.types import ChangeReason
from haywire.core.node.base import BaseNode
from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.node_wrapper import NodeWrapper

from haywire.ui.editor.event_definitions import SyncNodePositionEvent
from haywire.ui.ui_nodecard import UINodeCard
from haywire.ui.renderer.factory import RenderFactory, NO_RENDERER_DEFINED

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
        self.factory: RenderFactory = factory
        self.container: ui.element = container

        self._position: Optional[tuple[int, int]] = None
        
        # Container slot for reliable cleanup
        self.container_slot: Optional[ui.column] = None
        
        # Current UI representation
        self.current_ui_card: Optional[UINodeCard] = None
        
        # Generate unique ID for this UINode
        self.ui_node_id = f"ui-node-{id(self)}"

        self._node_id = self.wrapper.node_id
        """Store the id for cleanup purposes"""

        self.container.client.on_disconnect(lambda: self.cleanup())

        self.sync_event_emitter: Optional[Callable[[Any], None]] = None

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

    def register_sync_event_emitter(self, emitter: Callable[[Any], None]):
        """
        Register a synchronization event emitter for UI updates.
        
        Args:
            emitter: Callable that emits sync events
        """
        self.sync_event_emitter = emitter

    def refresh(self, reason: ChangeReason):
        """
        Refresh the UI representation of the node.
        This forces a re-render using the current renderer.
        """
        self.render()  # Re-render with current renderer

    def _listen_on_factory_lifecycle_event(self) -> None:
        """
        Handle renderer hot reload notifications from NodeRenderFactory.        
        """
        self.render()

    def render(self) -> bool:
        """
        Render the node using the factory.
        
        This may be called from background threads (file watcher) or validation callbacks.
        We always use container.client context to ensure UI updates run correctly.
        """
        # Always use the container's client context for safe rendering
        # This handles both initial renders and background task updates
        if not self.container or not hasattr(self.container, 'client'):
            logging.error(f"Cannot render UINode {self._node_id}: no valid container")
            return False
            
        with self.container.client:
            return self._render()

    def _render(self) -> bool:
        """
        Render the node using the specified renderer.
        
        Note: Must be called within a valid NiceGUI client context.
        """
        renderer_name = self.wrapper.node.settings.node.renderer

        if renderer_name is None:
            renderer_name = (
                self.factory._renderer_registry
                .get_default_renderer_registry_key()
            )

        try:
            # Clean up old widgets before clearing UI
            if self.current_ui_card:
                self.current_ui_card.cleanup()
            
            # Create or clear the container slot
            # We're already in the correct client context from render()
            if self.container_slot:
                self.container_slot.clear()  # NiceGUI handles cleanup reliably
            else:
                with self.container:
                    self.container_slot = ui.column().classes('ui-node-slot').props(
                        f'id="{self.ui_node_id}"'
                    )
            
            # Render into the container slot
            with self.container_slot:
                _is_error_render = False
                error = None

                if renderer_name is None:
                    # this can happen if :
                    # the node has no renderer assigned AND the registry has no default renderer available                        
                    renderer_name = NO_RENDERER_DEFINED  # Fallback if no default renderer is set"
                    logging.debug(
                        f"For node '{self.wrapper.node.identity.label}' - '{self.wrapper.node_id}' "
                        f"no render or default defined. Using '{NO_RENDERER_DEFINED}' as renderer key"
                    )

                # Subscribe to factory lifecycle events with the resolved renderer key
                # This handles re-subscription if renderer changes between renders
                self.factory.add_factory_lifecycle_subscriber(
                    self.wrapper.node_id,
                    renderer_name,
                    self._listen_on_factory_lifecycle_event
                )

                if renderer_name == NO_RENDERER_DEFINED:
                    error =  HaywireException.create(
                        category="Renderer Lookup Error",
                        operation="renderer_lookup",
                        message=(
                            f"For node '{self.wrapper.node.identity.label}' | '{self.wrapper.node_id}': "
                            f" No renderer registry key provided and no default renderer "
                            f"has been set in the renderer registry."
                        ),
                        suggestions=[
                            "Provide a valid renderer registry key",
                            "Set a default renderer for the registry",
                            "Check if the default renderer has failed to load"
                        ]
                    ).log()
                    _is_error_render = True
                    # we fallback to error renderer and hope for the best
                    renderer_name = self.factory._renderer_registry.get_error_renderer_registry_key()

                self.current_ui_card = self.factory.render(
                    renderer_name,
                    self.wrapper,
                    _is_error_render=_is_error_render
                )

                if error:
                    self.current_ui_card.append(error)  # Append error details if any

                self._emit_sync_event()
                
                return True  # Render successful
        except Exception as e:
            # Clean up old widgets before clearing UI
            if self.current_ui_card:
                self.current_ui_card.cleanup()
            
            # Clear the container slot on error
            if self.container_slot:
                try:
                    self.container_slot.clear()
                except:
                    pass  # Ignore errors during error cleanup

            self.container_slot = None

            HaywireException.from_exception(
                exception=e,
                message=f"FATAL Error rendering node: {e}",
                category="FATAL Rendering Error",
                operation="UINode.render",
            ).enrich(
                registry_key=renderer_name
            ).log()

            return False    

    def _emit_sync_event(self):
        """
        Emit a synchronization event for UI updates if emitter is registered.
        This updateds the vue component position to match the HaywireNode position
        but most importantly updates all the connection lines.
        """
        logging.debug(f"UINode {self.wrapper.node_id}: Emitting sync event for position update.")
        if self.sync_event_emitter:
            node = self.wrapper.node
            sync_event = SyncNodePositionEvent(
                nodeId=node.node_id,
                position={'x': node.ui.state.posX, 'y': node.ui.state.posY}
            )
            self.sync_event_emitter(sync_event)

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
        self.factory._unregister_node(self._node_id)
        # Clean up this session resources
        self.cleanup()

    def cleanup(self):
        """
        Clean up resources and remove UI elements.
        Enhanced to unsubscribe from wrapper and factory callbacks.
        """
        logging.info(f"🔌 Cleaning up UINode {self._node_id} ..")
        self.factory.remove_factory_lifecycle_subscriber(
            self._node_id,
            self._listen_on_factory_lifecycle_event
        )

        
        # Clean up widgets before clearing UI
        if self.current_ui_card:
            self.current_ui_card.cleanup()
        
        # Clear the container slot (reliable cleanup)
        if self.container_slot:
            try:
                self.container_slot.clear()
                # Optionally remove the container itself
                self.container_slot.delete()
            except Exception as e:
                self.logger.warning(f"Failed to clean up container slot: {e}", exc_info=True)
            self.container_slot = None
        
        # Clear references
        self.current_ui_card = None

        # Unsubscribe from wrapper changes

        logging.info(f".. Done 🔌 Cleaning up UINode {self._node_id}.")

        self.wrapper = None

    def is_rendered(self) -> bool:
        """Check if the node is currently rendered."""
        return self.current_ui_card is not None and self.container_slot is not None
    
    def get_node_data(self) -> BaseNode:
        """Get the underlying HaywireNode data."""
        return self.wrapper.node
    
    def get_ui_node_id(self) -> str:
        """Get the unique UI node ID."""
        return self.ui_node_id
