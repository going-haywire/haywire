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
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.types import ChangeReason
from haywire.core.node.base import BaseNode
from haywire.core.node.layout import PATCH, LayoutChannel
from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.node_wrapper import NodeWrapper

from haywire.ui.skin.factory import SkinFactory, NO_SKIN_DEFINED
from haywire.ui.skin.nodecard import UINodeCard

from haywire.ui.components.cull.cull import NodeCull
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

    Whoever creates a UINode tears it down (``teardown_subscriptions``); it
    registers nothing on the client.
    """

    # Class default too, so an instance built without __init__ reads the patch.
    channel: LayoutChannel = PATCH

    def __init__(
        self,
        container: ui.element,
        wrapper: NodeWrapper,
        factory: SkinFactory,
        route: EditRoute | None,
        channel: LayoutChannel = PATCH,
    ):
        """
        Initialize UINode with node, factory, and parent component.

        Args:
            wrapper: NodeWrapper for hot reload support
            component: Parent NiceGUI component to render into
            factory: SkinFactory for creating UI representations
            route: This session's edit route at the card's level. The card's
                widgets write through it, at level mode operate; ``None`` refuses
                every write.
            channel: The layout fields this card's size is read from.
        """
        self.channel = channel
        self.wrapper: NodeWrapper = wrapper
        self.factory: SkinFactory = factory
        self.container: ui.element = container
        self._route = route

        self._position: Optional[tuple[float, float]] = None

        # Container slot for reliable cleanup
        self.container_slot: Optional[ui.column] = None

        # Current UI representation
        self.current_ui_card: Optional[UINodeCard] = None

        # Generate unique ID for this UINode
        self.ui_node_id = f"ui-node-{id(self)}"

        self._node_id = self.wrapper.node_id
        """Store the id for cleanup purposes"""

        self.sync_event_emitter: Optional[Callable[[Any], None]] = None

        self._bound_node: Optional[BaseNode] = None
        self._subscribe_slot_fields()
        self._apply_locked_attr()
        self._apply_detail_attr()
        self._apply_enterable_attr()
        self._apply_stacking()

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
        self._rebind_props()
        renderer_name = self._skin_key()

        try:
            # Clean up old widgets before clearing UI
            if self.current_ui_card:
                self.current_ui_card.cleanup()

            # Create or clear the container slot
            # We're already in the correct client context from render()
            if self.container_slot:
                self.container_slot.clear()  # NiceGUI handles cleanup reliably
            else:
                # SPIKE: NodeCull sits between the positioned container (which keeps
                # data-node-id / left / top / the data-node-props-* attrs) and the
                # card, so withholding its slot drops this node's ~84 elements from
                # the page's render walk without moving anything the canvas queries.
                with self.container:
                    self._cull = NodeCull()
                with self._cull:
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
                    renderer_name,
                    self.wrapper,
                    on_stage=self.channel.stage,
                    _is_error_render=_is_error_render,
                    route=self._route,
                )

                if error and self.current_ui_card is not None:
                    self.current_ui_card.append(error)  # Append error details if any

                self._emit_sync_event_redraw()
                self._apply_slot_style()
                # A skin change may change whether the card honours the node's detail.
                self._apply_detail_attr()

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
        """Watch every prop that restyles the slot rather than redrawing it.

        Binds to the wrapper's current node instance. A rebuild replaces that
        instance, and its props drop their subscriptions with it, so
        :meth:`_rebind_props` calls this again for the new one.
        """
        node = self.wrapper.node
        props = node.props
        channel = self.channel
        self._bound_node = node
        for field_name in (
            channel.width,
            channel.height,
            channel.size_adapt,
            "node_theme",
            "color_override",
        ):
            props._subscribe_field(field_name, self._on_slot_field_change)
        # `locked` rides its own handler: it stamps the CONTAINER, not the slot,
        # because canvas.vue reads it off `[data-node-id]` when deciding what a
        # drag picks up — and custom attributes, unlike CSS vars, do not
        # inherit down to it from an ancestor.
        props._subscribe_field("locked", self._on_locked_change)
        # `detail` rides its own handler, same as `locked`: it stamps the
        # CONTAINER (not the slot), because canvas.vue's [data-node-props-detail]
        # rules key off it the same way [data-node-props-locked] does — and
        # custom attributes do not inherit down to descendants the way CSS
        # vars do.
        props._subscribe_field("detail", self._on_detail_change)
        props._subscribe_field(channel.z, self._on_stacking_change)

    def _on_locked_change(self, _value: Any, _old: Any) -> None:
        self._apply_locked_attr()

    def _on_detail_change(self, _value: Any, _old: Any) -> None:
        self._apply_detail_attr()

    def _on_stacking_change(self, _value: Any, _old: Any) -> None:
        self._apply_stacking()

    def _unsubscribe_slot_fields(self) -> None:
        """Detach this card's prop handlers from the node it is bound to."""
        node = self._bound_node
        self._bound_node = None
        if node is None:
            return
        props = node.props
        for callback in (
            self._on_slot_field_change,
            self._on_locked_change,
            self._on_detail_change,
            self._on_stacking_change,
        ):
            props._unsubscribe(callback)

    def _rebind_props(self) -> None:
        """Follow the wrapper to its current node instance.

        Does nothing while the card is still bound to the live instance.
        Otherwise detaches from the old one, subscribes to the new one and
        restamps the container attributes from its props.
        """
        if self._bound_node is self.wrapper.node:
            return
        self._unsubscribe_slot_fields()
        self._subscribe_slot_fields()
        self._apply_locked_attr()
        self._apply_detail_attr()
        self._apply_stacking()

    def _apply_locked_attr(self) -> None:
        """Stamp ``data-node-props-locked`` on the container for canvas.vue to read.

        Present-and-"true" only when locked; removed entirely otherwise, so the
        client can test presence rather than parse a value. The gesture guards
        (drag pickup, resize gadget) live in canvas.vue — this is the only
        thing that tells them which nodes are locked.

        The ``data-node-props-`` prefix is the convention for an attribute that
        mirrors a ``NodeProperties`` field, so the reader can find its source
        from the name alone. canvas.vue carries the full index of these
        attributes at the top of its ``<script>``; add to it when adding one.
        """
        if self.wrapper.node.props.locked:
            self.container._props["data-node-props-locked"] = "true"
        else:
            self.container._props.pop("data-node-props-locked", None)
        self.container.update()

    def _apply_stacking(self) -> None:
        """Write the node's stacking order in this card's channel as the container's z-index.

        Cards that share a value paint in DOM order. See ``haywire.core.graph.stacking``.
        """
        z = getattr(self.wrapper.node.props, self.channel.z)
        self.container.style(f"z-index: {z}")
        self.container.update()

    def _apply_enterable_attr(self) -> None:
        """Stamp ``data-node-enterable`` on the container of a Group or macro placement card.

        canvas.vue enters the card on a double-click. A card's kind is fixed
        for its lifetime, so one stamp at construction is enough.
        """
        from haywire.core.macro.source import is_macro_placement

        node = self.wrapper.node
        if node.identity._is_graph_node or is_macro_placement(node):
            self.container._props["data-node-enterable"] = "true"
            self.container.update()

    def _skin_key(self) -> Optional[str]:
        """Return the registry key of the skin this view draws the node with.

        A stage canvas reads ``props.stage_skin``, a patch canvas ``props.skin``.
        An unset value falls back to the registry's default skin; ``None`` when the
        registry has none.
        """
        props = self.wrapper.node.props
        key = props.stage_skin if self.channel.stage else props.skin
        return key or self.factory._skin_registry.get_default_skin_registry_key()

    def _skin_honours_detail(self) -> bool:
        """Whether the skin this view draws with follows the node's Detail setting here.

        ``True`` when the skin cannot be resolved.
        """
        key = self._skin_key()
        try:
            skin = self.factory.get_skin_instance(key) if key else None
        except Exception:
            return True
        return skin is None or bool(skin.honours_detail(on_stage=self.channel.stage))

    def _apply_detail_attr(self) -> None:
        """Stamp ``data-node-props-detail`` on the container for canvas.vue to read.

        Unlike ``locked`` (presence-tested), this is ALWAYS present — every
        node resolves to some ``NodeDetail`` rank, so the client never has to
        distinguish "absent" from "at the floor rank". Value is the resolved
        rank's wire string (``NodeDetail.coerce`` already degrades anything
        unreadable to ``FULL``), read once here rather than re-deriving the
        resolution logic client-side.

        The ``data-node-props-`` prefix is the convention for an attribute that
        mirrors a ``NodeProperties`` field — see the attribute index at the top
        of canvas.vue's ``<script>``; this entry was added there alongside this
        method.
        """
        from haywire.core.types import NodeDetail

        detail = NodeDetail.coerce(self.wrapper.node.props.detail)
        if not self._skin_honours_detail():
            detail = NodeDetail.FULL
        self.container._props["data-node-props-detail"] = detail.value
        self.container.update()

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
        ``data-node-props-size-adapt`` is stamped so the client-side observer
        can skip manual axes and the card-fill CSS (canvas.vue) can key off it.
        Unlike its siblings this one is NOT write-only: canvas.vue flips it
        during a resize drag, so treat it as shared state. See the attribute
        index at the top of canvas.vue's ``<script>``.

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
        channel = self.channel
        mode = getattr(props, channel.size_adapt)
        manual_w = mode in ("manual_width", "manual")
        manual_h = mode in ("manual_height", "manual")

        decls: list[str] = []
        if manual_w:
            decls.append(f"min-width: {getattr(props, channel.width)}px")
        if manual_h:
            decls.append(f"min-height: {getattr(props, channel.height)}px")

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
        self.container_slot._props["data-node-props-size-adapt"] = mode
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
        self._unsubscribe_slot_fields()
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
