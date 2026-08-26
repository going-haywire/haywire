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

from haywire.ui.skin.factory import SkinFactory, NO_SKIN_DEFINED
from haywire.ui.skin.nodecard import UINodeCard

from haywire.ui.components.graph.event_definitions import SyncNodeRedrawEvent

logger = logging.getLogger(__name__)


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

        self._position: Optional[tuple[float, float]] = None

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

        self._subscribe_slot_fields()

    @property
    def position(self) -> Optional[tuple[float, float]]:
        return self._position

    @position.setter
    def position(self, value: tuple[float, float]):
        self._position = value

    def set_position(self, position: tuple[float, float]):
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
        renderer_name: Optional[str] = self.wrapper.node.props.skin

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
                    renderer_name = (
                        self.factory._skin_registry.get_error_skin_registry_key() or NO_SKIN_DEFINED
                    )

                self.current_ui_card = self.factory.render(
                    renderer_name, self.wrapper, _is_error_render=_is_error_render
                )

                if error and self.current_ui_card is not None:
                    self.current_ui_card.append(error)  # Append error details if any

                self._emit_sync_event_redraw()
                self._apply_slot_style()

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

    def _on_slot_field_change(self, _value: Any, _old: Any) -> None:
        """A size or appearance prop changed → restyle the slot. NEVER a redraw.

        This is the loop-breaker: measurement (ResizeObserver) writes props,
        which lands here and only restyles the slot — no card rebuild, so no
        re-measure cascade. Appearance rides the same path for the same reason
        turned inside out: rebuilding the card on a colour keystroke destroys
        the input being typed into.
        """
        self._apply_slot_style()

    def _subscribe_slot_fields(self) -> None:
        """Watch every prop that restyles the slot rather than redrawing it."""
        props = self.wrapper.node.props
        for field_name in ("width", "height", "size_adapt", "node_theme", "color_override"):
            props.subscribe_field(field_name, self._on_slot_field_change)

    def _node_theme_declarations(self) -> list[str]:
        """This node's theme as CSS var declarations — empty unless it diverges.

        Divergence is decided by comparing the node's resolved ``node_theme``
        against the graph's, NOT by asking whether the field is locally set:
        identical values produce identical CSS, so writing them is pure waste
        however they arose. On a large graph that waste is the difference
        between one declaration set and one per node.

        Every token the theme declares is emitted, selection-ring/active-
        outline/shadow included. Those three are structurally inert here —
        they're consumed by canvas.vue on ``[data-node-id]``, an ANCESTOR of
        this slot, and custom properties inherit downward only — but the node
        tier writes them anyway rather than filtering them out, so a theme
        author sees the same to_css_vars() output land at every tier
        uniformly. Put selection/active/shadow changes on the graph or global
        tier to actually see them.
        """
        props = self.wrapper.node.props
        node_key = getattr(props, "node_theme", "") or ""
        if not node_key:
            return []

        graph = getattr(self.wrapper, "graph", None)
        graph_key = getattr(getattr(graph, "props", None), "node_theme", "") or ""
        if node_key == graph_key:
            return []

        try:
            from haywire.core.di.config import get_theme_registry

            theme = get_theme_registry().get_node_theme(node_key)
        except Exception:
            # An unknown or unresolvable theme key must not take the node's
            # whole render down — it simply contributes nothing, so the tier
            # above shows through.
            logger.warning("Node %s: unresolvable node_theme %r", self._node_id, node_key)
            return []

        return [f"{var}: {val}" for var, val in theme.to_css_vars().items()]

    def _apply_slot_style(self) -> None:
        """Apply size AND appearance to the host slot as one style-write.

        A ``manual`` axis is a user-defined MINIMUM: written as inline
        ``min-width``/``min-height``, so the node draws at that size but content
        needing more space expands it — nothing is ever clipped (pins, widgets
        and attached edges stay intact). An ``auto`` axis carries no inline
        size, so the slot sizes to its card's content and the ResizeObserver
        (see :meth:`_attach_size_observer`) measures it back into props.
        ``data-size-adapt`` is stamped so the client-side observer can skip
        manual axes and the card-fill CSS (canvas.vue) can key off it.

        Size and appearance MUST share this one method: the write below is
        ``replace=``, deliberately authoritative, so a second writer using
        ``add=`` would be silently wiped on the next size change.

        Order matters at the end: ``color_override`` is composed last so an
        explicit highlight wins over the node's own theme. Later declarations
        of the same custom property in one style attribute win.

        Idempotent: called after every render and on every slot-field change.
        """
        if not self.container_slot:
            return
        props = self.wrapper.node.props
        mode = props.size_adapt
        manual_w = mode in ("manual_width", "manual")
        manual_h = mode in ("manual_height", "manual")

        decls: list[str] = []
        if manual_w:
            decls.append(f"min-width: {props.width}px")
        if manual_h:
            decls.append(f"min-height: {props.height}px")

        decls += self._node_theme_declarations()

        # Emptiness is the whole "unset" mechanism — no is_locally_set needed.
        override = getattr(props, "color_override", None)
        if override:
            decls.append(f"--hw-node-bg: {override}")

        # replace= (not add=) so the write is authoritative every call: an
        # auto axis clears any inline width/height a prior manual mode left,
        # and a cleared colour clears its var, rather than merging stale
        # declarations.
        self.container_slot.style(replace="; ".join(decls))
        self.container_slot._props["data-size-adapt"] = mode
        self.container_slot.update()

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

    def delete(self):
        """Tear down subscriptions and remove the node's DOM. For single-node
        removal (``remove_node_visual``).
        """
        self.teardown_subscriptions()
        self.delete_dom()

    def cleanup(self):
        """Subscriptions-only teardown (alias of :meth:`teardown_subscriptions`)."""
        self.teardown_subscriptions()

    def teardown_subscriptions(self):
        """Detach this node's factory tracking, lifecycle subscriber, and widget
        callbacks. Does NOT touch the DOM. Idempotent.
        """
        logger.debug(f"🔌 Tearing down subscriptions for UINode {self._node_id} ..")
        self.factory._unregister_node(self._node_id)
        self.factory.remove_factory_lifecycle_subscriber(
            self._node_id, self._listen_on_factory_lifecycle_event
        )
        if self.current_ui_card:
            self.current_ui_card.cleanup()
        self.current_ui_card = None
        logger.debug(f".. Done 🔌 subscription teardown for UINode {self._node_id}.")

    def delete_dom(self):
        """Remove this node's container DOM. For single-node deletion only;
        the bulk close path relies on the container teardown instead.
        """
        if self.container_slot:
            try:
                self.container_slot.clear()
                self.container_slot.delete()
            except Exception as e:
                logger.warning(f"Failed to clean up container slot: {e}", exc_info=True)
            self.container_slot = None
        if self.container:
            try:
                self.container.delete()
            except Exception as e:
                logger.warning(f"Failed to delete node container: {e}", exc_info=True)

    def is_rendered(self) -> bool:
        """Check if the node is currently rendered."""
        return self.current_ui_card is not None and self.container_slot is not None

    def get_node_data(self) -> BaseNode:
        """Get the underlying HaywireNode data."""
        return self.wrapper.node

    def get_ui_node_id(self) -> str:
        """Get the unique UI node ID."""
        return self.ui_node_id
