"""
UINode - Manager class for node UI lifecycle with reliable cleanup and hot reload support

This class manages the relationship between a HaywireNode and its UI representation,
using a container-slot approach for reliable re-rendering and cleanup.

Enhanced with hot reload support: UINode subscribes to NodeWrapper change callbacks
and automatically re-renders when the underlying node class is hot-reloaded.
"""

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)
from nicegui import ui
from haywire.core.graph.types import ChangeReason
from haywire.core.node.base import BaseNode
from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.node_wrapper import NodeWrapper

from haywire.ui.graph_canvas.event_definitions import SyncNodeRedrawEvent
from haywire.ui.ui_nodecard import UINodeCard
from haywire.ui.skin.factory import SkinFactory, NO_SKIN_DEFINED


class UINode:
    """
    Manages the lifecycle and rendering of a HaywireNode's UI representation.

    This class:
    - Holds references to HaywireNode and SkinFactory
    - Uses container-slot approach for reliable cleanup during re-rendering
    - Delegates all rendering logic to the factory
    - Has no knowledge of skins or widgets (clean separation)
    - Subscribes to NodeWrapper for hot reload support
    """

    def __init__(self, container: ui.element, wrapper: NodeWrapper, factory: SkinFactory):
        """
        Initialize UINode with node, factory, and parent component.

        Args:
            wrapper: NodeWrapper for hot reload support
            component: Parent NiceGUI component to render into
            factory: SkinFactory for creating UI representations
        """
        self.wrapper: NodeWrapper = wrapper
        self.factory: SkinFactory = factory
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
        Handle skin hot reload notifications from SkinFactory.
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
        if not self.container or not hasattr(self.container, "client"):
            logger.error(f"Cannot render UINode {self._node_id}: no valid container")
            return False

        with self.container.client:
            return self._render()

    def _render(self) -> bool:
        """
        Render the node using the specified renderer.

        Note: Must be called within a valid NiceGUI client context.
        """
        renderer_name = self.wrapper.node.props.skin

        if renderer_name is None:
            renderer_name = self.factory._skin_registry.get_default_skin_registry_key()

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
                    self.container_slot = (
                        ui.column().classes("ui-node-slot").props(f'id="{self.ui_node_id}"')
                    )

            # Render into the container slot
            with self.container_slot:
                _is_error_render = False
                error = None

                if renderer_name is None:
                    # this can happen if :
                    # the node has no skin assigned AND the registry has no default skin available
                    renderer_name = NO_SKIN_DEFINED  # Fallback if no default skin is set
                    logger.debug(
                        f"For node '{self.wrapper.node.identity.label}' - '{self.wrapper.node_id}' "
                        f"no skin or default defined. Using '{NO_SKIN_DEFINED}' as skin key"
                    )

                # Subscribe to factory lifecycle events with the resolved renderer key
                # This handles re-subscription if renderer changes between renders
                self.factory.add_factory_lifecycle_subscriber(
                    self.wrapper.node_id, renderer_name, self._listen_on_factory_lifecycle_event
                )

                if renderer_name == NO_SKIN_DEFINED:
                    error = HaywireException.create(
                        category="Skin Lookup Error",
                        operation="skin_lookup",
                        message=(
                            f"For node '{self.wrapper.node.identity.label}' | '{self.wrapper.node_id}': "
                            f" No skin registry key provided and no default skin "
                            f"has been set in the skin registry."
                        ),
                        suggestions=[
                            "Provide a valid skin registry key",
                            "Set a default skin for the registry",
                            "Check if the default skin has failed to load",
                        ],
                    ).log()
                    _is_error_render = True
                    # we fallback to error skin and hope for the best
                    renderer_name = self.factory._skin_registry.get_error_skin_registry_key()

                self.current_ui_card = self.factory.render(
                    renderer_name, self.wrapper, _is_error_render=_is_error_render
                )

                if error:
                    self.current_ui_card.append(error)  # Append error details if any

                self._emit_sync_event_redraw()

                return True  # Render successful
        except Exception as e:
            # Clean up old widgets before clearing UI
            if self.current_ui_card:
                self.current_ui_card.cleanup()

            # Clear the container slot on error
            if self.container_slot:
                try:
                    self.container_slot.clear()
                except Exception:
                    pass  # Ignore errors during error cleanup

            self.container_slot = None

            HaywireException.from_exception(
                exception=e,
                message=f"FATAL Error rendering node: {e}",
                category="FATAL Rendering Error",
                operation="UINode.render",
            ).enrich(registry_key=renderer_name).log()

            return False

    def _emit_sync_event_redraw(self):
        """
        Emit a redraw event after the node DOM has been rebuilt.
        Vue will re-attach the hover observer and redraw all connected edges,
        using the pending-set / MutationObserver pattern if the canvas is not
        currently the active panel.
        """
        logger.debug(f"UINode {self.wrapper.node_id}: Emitting sync redraw event.")
        if self.sync_event_emitter:
            sync_event = SyncNodeRedrawEvent(nodeId=self.wrapper.node_id)
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
        logger.info(f"🔌 Cleaning up UINode {self._node_id} ..")
        self.factory.remove_factory_lifecycle_subscriber(
            self._node_id, self._listen_on_factory_lifecycle_event
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
                logger.warning(f"Failed to clean up container slot: {e}", exc_info=True)
            self.container_slot = None

        # Clear references
        self.current_ui_card = None

        # Unsubscribe from wrapper changes

        logger.info(f".. Done 🔌 Cleaning up UINode {self._node_id}.")

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
