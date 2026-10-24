"""
GraphCanvasManager — facade that wires handler objects to the Vue canvas.

Public API is unchanged; all event-handling and visual-management logic has
been moved into focused handler classes under handlers/.
"""

import asyncio
import logging
import traceback
from typing import Callable, Dict, Optional, Set
from nicegui import background_tasks, ui

from haywire.core.access import LevelMode
from haywire.core.graph.edit_route import EditRoute
from haywire.core.graph.types import ValidationResult
from haywire.core.node.layout import PATCH, LayoutChannel

from haywire.ui.components.zoom.pan import ZoomPanContainer
from haywire.ui.components.graph.canvas import GraphCanvasVue
from haywire.ui.components.graph.event_definitions import (
    BaseGraphEvent,
    ContextMenuCanvasEvent,
    ContextMenuEdgeEvent,
    ContextMenuPortEvent,
    ContextMenuSelectedEvent,
    ContextMenuSurfaceEvent,
    EdgeClickedEvent,
    EdgeCreatedEvent,
    EdgeReconnectStartedEvent,
    EnterGroupEvent,
    GRAPH_EVENT_REGISTRY,
    SelectionChangedEvent,
    UserDragEndEvent,
    UserDragStartEvent,
    UserPasteClipboardEvent,
    UserResizeEndEvent,
)
from haywire.core.session.session import Session
from haywire.core.signals import SelectionMoved

from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.editors.graph_canvas.event_handlers import (
    build_event_handler_map,
    handler_requires,
)
from haybale_graph_editor.editors.graph_canvas.graph_load_modal import graph_load_modal
from haybale_graph_editor.editors.graph_canvas.handlers.interaction import InteractionHandlers
from haybale_graph_editor.editors.graph_canvas.handlers.selection import (
    SelectionHandlers,
    copy_selection_event,
    remove_selection_event,
)
from haybale_graph_editor.editors.graph_canvas.handlers.visual_layer import VisualLayerHandlers
from haybale_graph_editor.editors.graph_canvas.handlers.context_menu import (
    ContextMenuHandlers,
    SessionContextMenuProvider,
)
from haybale_graph_editor.editors.graph_canvas.handlers.selection_toolbar import (
    SelectionToolbarProvider,
    SelectionToolbarHandlers,
)

logger = logging.getLogger(__name__)

POINTER_GESTURE_EVENTS: frozenset[type[BaseGraphEvent]] = frozenset(
    {
        SelectionChangedEvent,
        ContextMenuCanvasEvent,
        ContextMenuEdgeEvent,
        ContextMenuSelectedEvent,
        ContextMenuSurfaceEvent,
        ContextMenuPortEvent,
        EdgeClickedEvent,
        EdgeReconnectStartedEvent,
        EdgeCreatedEvent,
        UserDragStartEvent,
        UserResizeEndEvent,
        EnterGroupEvent,
    }
)
"""The canvas events only a user's pointer gesture on the canvas sends; each reports ``on_user_event``.

Events the canvas sends on its own (mount, measurement, selection bounds on a
wheel zoom or a node removal) are not in it.
"""


class GraphCanvasManager:
    """
    Facade that wires canvas event handlers and the Vue component together.

    Responsibilities kept here:
    - Canvas/zoom/menu construction (_setup_canvas)
    - Building and connecting handler objects
    - Event dispatch (build_event_handler_map + _handle_canvas_event)
    - Public facade methods (sync_with_graph, cleanup, …)

    All domain logic lives in the handler sub-objects:
    - visual_layer  → VisualLayerHandlers
    - selection     → SelectionHandlers
    - interactions  → InteractionHandlers
    - context_menus → ContextMenuHandlers
    """

    def refresh_mode(self) -> None:
        """Push the level mode of this canvas's route to the browser.

        Below ``EDIT`` the selection toolbar is hidden and an open context menu is
        closed; the selection stays. Reaching ``EDIT`` reopens nothing here: the
        browser re-reports the selection's bounds, which shows the toolbar.
        """
        mode = self.route.mode()
        self.canvas_vue.set_level_mode(mode)
        if mode is not LevelMode.EDIT:
            self._toolbar_provider.hide()
            self.context_menu_handlers.provider.close_open_menu()

    def viewport_centre(self) -> Optional[tuple[float, float]]:
        """The canvas position at the middle of the last-known viewport, or ``None``.

        The viewport is the last one the client reported, so a canvas that never mounted in a
        browser has none. In this canvas's own coordinates, as ``create_wrapper`` takes them.
        """
        return self.zoom_container.get_viewport_centre()

    # Class default too, so an instance built without __init__ dispatches without reporting.
    _on_user_event: Optional[Callable[[], None]] = None
    # Likewise: an instance built without __init__ is a patch canvas.
    channel: LayoutChannel = PATCH

    def __init__(
        self,
        route: EditRoute,
        skin_factory,
        node_factory,
        panel_registry,
        session: "Session",
        on_user_event: Optional[Callable[[], None]] = None,
        channel: LayoutChannel = PATCH,
        patch_viewport_centre: Optional[Callable[[], Optional[tuple[float, float]]]] = None,
    ):
        """Build the canvas for ``route``'s graph into the current slot, in ``route``'s level mode.

        Args:
            route: This session's edit route at the level; every edit the canvas makes goes
                through it.
            on_user_event: Called with no arguments before an event in
                ``POINTER_GESTURE_EVENTS`` is dispatched, whether or not its
                handler then runs. ``None`` reports nothing.
            channel: The props fields this canvas lays its nodes out with.
            patch_viewport_centre: On a stage canvas, returns where the level's patch canvas
                is looking (see ``viewport_centre``), or ``None``; places nodes made on an
                empty stage.
        """
        self.channel = channel
        self.route = route
        self._on_user_event = on_user_event
        self.skin_factory = skin_factory
        self.node_factory = node_factory
        self._panel_registry = panel_registry
        self._session = session
        self.session_id = session.session_id[:8]

        self.graph = route.graph

        # In-flight chunked load, if any — cancelled by cleanup(). See
        # start_chunked_sync.
        self._sync_task: Optional[asyncio.Task] = None

        # Vue component references built in _setup_canvas
        self.zoom_container, self.canvas_vue = self._setup_canvas()

        # Build handler objects
        self.visual_layer = VisualLayerHandlers(
            graph=self.graph,
            route=self.route,
            skin_factory=self.skin_factory,
            canvas_vue=self.canvas_vue,
            context=self._session.context,
            channel=self.channel,
            patch_viewport_centre=patch_viewport_centre,
        )
        self.selection = SelectionHandlers(
            graph=self.graph,
            route=self.route,
            session_id=self.session_id,
            session=self._session,
            visual_layer=self.visual_layer,
            channel=self.channel,
            patch_viewport_centre=patch_viewport_centre,
        )
        self.visual_layer.on_node_unmounted = self.selection.prune_node
        self.visual_layer.on_canvas_mounted = self._reshow_selection
        self.interactions = InteractionHandlers(
            route=self.route, session=self._session, channel=self.channel
        )

        context_menu_provider = SessionContextMenuProvider(
            context=self._session.context,
            session=self._session,
            panel_registry=self._panel_registry,
            on_emit_event=self._handle_canvas_event,
            on_emit_sync_event=self.canvas_vue.emit_sync_event,
            canvas_vue=self.canvas_vue,
        )

        self.context_menu_handlers = ContextMenuHandlers(
            visual_layer=self.visual_layer,
            provider=context_menu_provider,
        )

        self._toolbar_provider = SelectionToolbarProvider(
            context=self._session.context,
            session=self._session,
            panel_registry=self._panel_registry,
            on_emit_event=self._handle_canvas_event,
            on_emit_sync_event=self.canvas_vue.emit_sync_event,
            # SelectionToolbar.provides is SelectionActions; the toolbar
            # forwards every verb it does not emit itself to the menu
            # provider, which already implements them against the same
            # canvas. Delegation, not duplication (ADR-0029).
            menu_provider=context_menu_provider,
            allows=self.route.allows,
        )
        self.toolbar_handlers = SelectionToolbarHandlers(provider=self._toolbar_provider)

        # Build dispatch map from all handler sources
        self._event_handlers: Dict[str, Callable] = build_event_handler_map(
            [
                self.visual_layer,
                self.selection,
                self.interactions,
                self.context_menu_handlers,
                self.toolbar_handlers,
            ]
        )

        self._validate_handler_coverage()
        self._push_gesture_requires()

        # Subscribe for incremental validation updates
        self.graph.subscribe_to_validation(self.visual_layer.on_validated)
        self.graph.subscribe_to_validation(self._refresh_toolbar_for)

        self._follow_graph_props()

        # A canvas first mounted on a level below edit starts in that mode, not in the browser's default.
        self.refresh_mode()

        logger.info(f"🔧 GraphCanvasManager for {self.session_id} is setup")

    def center_on_node(self, node_id: str) -> None:
        """Pan this canvas so the middle of the node's card sits in the middle of the viewport.

        The zoom stays. Does nothing when this canvas does not show the node, and the browser
        does nothing while the canvas is not on screen.
        """
        wrapper = self.graph.get_node_wrapper(node_id)
        if wrapper is None or not self.visual_layer.shows_node(node_id):
            return
        props = wrapper.node.props
        channel = self.channel
        x, y = channel.to_canvas(getattr(props, channel.x), getattr(props, channel.y))
        width = getattr(props, channel.width) or 0.0
        height = getattr(props, channel.height) or 0.0
        self.zoom_container.center_on(x + width / 2, y + height / 2)

    def _refresh_toolbar_for(self, result: ValidationResult) -> None:
        """Re-render the selection toolbar when ``result`` names a node or edge selected here.

        Every user edit of a node or edge, by any session, an agent, an undo or a redo,
        reaches a validation batch, so the toolbar shows what is true now.
        """
        selection = self.selection
        if selection.selected_nodes.isdisjoint(result.nodes) and selection.selected_edges.isdisjoint(
            result.edges
        ):
            return
        self._toolbar_provider.refresh()

    def _follow_graph_props(self) -> None:
        """Apply the graph's canvas-level props and follow later edits to them.

        :meth:`cleanup` releases the subscriptions made here; the graph outlives
        every canvas drawn for it.
        """
        # Graph-tier node theme: written once onto the canvas element, which is
        # an ancestor of every node card, so no per-node work is involved.
        self._apply_graph_node_theme()
        self.graph.props._subscribe_field("node_theme", self._on_node_theme_changed)

        # Computed-edge defaults: pushed as canvas props; canvas.vue turns them
        # into CSS vars and path insets, so a change costs one push per canvas.
        self._apply_edge_defaults()
        for field in ("edge_arrow", "edge_arrow_size", "edge_width"):
            self.graph.props._subscribe_field(field, self._on_edge_default_changed)

    def _on_node_theme_changed(self, _value, _old) -> None:
        self._apply_graph_node_theme()

    def _on_edge_default_changed(self, _value, _old) -> None:
        self._apply_edge_defaults()

    def _apply_edge_defaults(self) -> None:
        """Push this graph's computed-edge arrow head, head size and width to the canvas."""
        props = self.graph.props
        self.canvas_vue.set_edge_defaults(props.edge_arrow, props.edge_arrow_size, float(props.edge_width))

    def _apply_graph_node_theme(self) -> None:
        """Write this graph's node theme onto the canvas as CSS vars.

        The canvas element sits ABOVE ``[data-node-id]``, so unlike the per-node
        tier this one also reaches the Tier 2 tokens (selection ring, active
        outline, shadow) — custom properties inherit downward, and those rules
        live on an element the node's own slot cannot reach.

        Skipped entirely when the graph does not diverge from the global theme:
        identical values produce identical CSS, and :root already carries them.
        """
        graph_key = getattr(self.graph.props, "node_theme", "") or ""
        if not graph_key:
            self.canvas_vue.style(replace="")
            return

        try:
            from haywire.core.di.config import get_settings_registry, get_theme_registry

            global_key, _ = get_settings_registry().resolve("ui.node.default.skin.studio_node_theme")
            if graph_key == global_key:
                self.canvas_vue.style(replace="")
                return
            theme = get_theme_registry().get_node_theme(graph_key)
        except Exception:
            # An unresolvable key contributes nothing rather than breaking the
            # canvas — the global tier shows through.
            logger.warning("Graph node_theme %r could not be resolved", graph_key)
            self.canvas_vue.style(replace="")
            return

        decls = "; ".join(f"{var}: {val}" for var, val in theme.to_css_vars().items())
        self.canvas_vue.style(replace=decls)

    # =========================================================================
    # Setup
    # =========================================================================

    def _setup_canvas(self) -> tuple[ZoomPanContainer, GraphCanvasVue]:
        """Create zoom container and Vue canvas component."""
        zoom_container = (
            ZoomPanContainer()
            .classes("w-full flex-grow")
            .style("border: 2px solid var(--hw-border);")
            .style("height: 100%;")
        )

        canvas_width, canvas_height = self.graph.canvas_extent(self.channel)
        with zoom_container.content_container:
            canvas_vue = GraphCanvasVue(
                zoom_container=zoom_container,
                on_canvas_event=self._handle_canvas_event,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                origin=self.channel.origin,
                stage=self.channel.stage,
            )
        return zoom_container, canvas_vue

    def _push_gesture_requires(self) -> None:
        """Send the browser the level mode each event type's handler declares."""
        self.canvas_vue.set_gesture_requires(
            {event_type: handler_requires(handler) for event_type, handler in self._event_handlers.items()}
        )

    def _validate_handler_coverage(self):
        """Warn if any user event lacks a registered handler."""
        user_events = [
            event_type
            for event_type, event_class in GRAPH_EVENT_REGISTRY.items()
            if getattr(event_class, "category", "user") == "user"
        ]
        missing = [et for et in user_events if et not in self._event_handlers]
        if missing:
            logger.warning(f"⚠️  Missing handlers for events: {missing}")
        else:
            logger.debug(f"✅ All {len(user_events)} user events have registered handlers")

    # =========================================================================
    # Event routing
    # =========================================================================

    def _handle_canvas_event(self, event: BaseGraphEvent):
        """Dispatch a canvas event to its handler, if this session may run it here.

        A refused event changes nothing in the graph. A refused drag end also
        moves its nodes on screen back to their model positions, and a refused
        resize end its node back to its model position and size. An event in
        ``POINTER_GESTURE_EVENTS`` calls ``on_user_event`` first, refused or not.
        """
        if self._on_user_event is not None and type(event) in POINTER_GESTURE_EVENTS:
            self._on_user_event()
        event_type = event.event_type
        handler = self._event_handlers.get(event_type)

        if handler and not self.route.allows(needed := handler_requires(handler)):
            logger.debug(f"Refused {event_type}: needs {needed.value} (mode={self.route.mode().value})")
            if isinstance(event, UserDragEndEvent):
                self.visual_layer.resync_positions(event.nodes)
            elif isinstance(event, UserResizeEndEvent):
                self.visual_layer.resync_positions([event.nodeId])
                self.visual_layer.resync_size(event.nodeId)
            return

        if handler:
            handler_name = getattr(handler, "__name__", repr(handler))
            logger.debug(f"🔧 Calling handler for {event_type}: {handler_name}")
            try:
                handler(event)
            except Exception as e:
                logger.error(f"❌ Error calling handler for {event_type}: {e}")
                ui.notify(f"Error while processing {event.description}: {e}", type="negative")
                traceback.print_exc()
        else:
            logger.warning(f"No handler found for event type: {event_type}")

    # =========================================================================
    # Public facade — unchanged external API
    # =========================================================================

    def sync_with_graph(self):
        """Synchronise visual representation with the current graph state.

        Blocks the event loop for the whole mount. Larger graphs (>=
        ``CHUNKED_LOAD_THRESHOLD`` nodes) should call
        :meth:`start_chunked_sync` instead.
        """
        self.visual_layer.sync_with_graph()

    def start_chunked_sync(
        self,
        *,
        on_nodes_mounted: Optional[Callable[[], None]] = None,
        graph_name: str = "graph",
    ) -> None:
        """Mount the graph in the background behind a blocking load overlay.

        Returns immediately; the canvas fills in over the following seconds
        while the server stays responsive. ``on_nodes_mounted`` runs after the
        last node is mounted and before the edge batch goes out — the editor
        centres the viewport there, so the edges draw into a viewport that is
        already over the graph. It does NOT run if the load is cancelled.

        The overlay blocks canvas interaction for the whole load — see
        :mod:`.graph_load_modal` for why a partially-mounted canvas must not be
        touched — and is closed in a ``finally`` so it can never outlive the
        load and strand the user behind an undismissable backdrop.

        The task is retained so :meth:`cleanup` can cancel a load still running
        when the editor closes — otherwise it would keep mounting nodes into a
        torn-down canvas. A websocket drop does not cancel it: a drop the page
        reconnects from would leave it half-loaded. So a page reloaded mid-load
        keeps its old load running until the old client is deleted, after
        ``reconnect_timeout``.
        """
        modal = graph_load_modal(
            graph_name=graph_name,
            total_nodes=self.visual_layer.included_node_count(),
        )

        async def _run() -> None:
            try:
                await self.visual_layer.sync_with_graph_chunked(
                    on_progress=modal.advance,
                    on_phase=modal.set_phase,
                    on_nodes_mounted=on_nodes_mounted,
                )
            finally:
                # Unconditional: success, cancellation and failure all hand the
                # canvas back rather than leaving the overlay up forever.
                modal.close()
                self._sync_task = None

        self._sync_task = background_tasks.create(_run(), name=f"graph-sync-{self.session_id}")

    def resync_edges(self) -> None:
        """Re-emit every edge as one batch. See ``VisualLayerHandlers.resync_edges``."""
        self.visual_layer.resync_edges()

    def sync_selections(self):
        """Emit consolidated selection sync event to Vue."""
        self.visual_layer.sync_selections(
            self.selection.selected_nodes,
            self.selection.selected_edges,
        )

    def copy_selection(self) -> None:
        """Copy the selected nodes of this canvas's graph to the session and OS clipboards.

        Selected ids from other graphs are ignored. With no node of this graph
        selected, both clipboards keep their content.
        """
        nodes, edges = self._own_selection()
        if nodes:
            self._handle_canvas_event(copy_selection_event(nodes, edges))

    def delete_selection(self) -> None:
        """Remove the selection in this canvas's graph as one undoable step, skipping locked nodes.

        Selected ids from other graphs are ignored; with none of this graph's
        nodes or edges selected, nothing happens.
        """
        nodes, edges = self._own_selection()
        if nodes or edges:
            self._handle_canvas_event(remove_selection_event(nodes, edges))

    def cut_selection(self) -> None:
        """Copy the selection in this canvas's graph to the clipboards, then remove it.

        Behaves as ``copy_selection`` followed by ``delete_selection``; the
        removal is one undoable step.
        """
        self.copy_selection()
        self.delete_selection()

    def duplicate_selection(self) -> None:
        """Duplicate the selected nodes of this canvas's graph next to them and select the copy.

        Selected ids from other graphs are ignored. The clipboards keep their
        content. See ``SelectionHandlers.duplicate_selection``.
        """
        nodes, edges = self._own_selection()
        if nodes:
            self.selection.duplicate_selection(nodes, edges)

    def paste(self, position: tuple[float, float], text: str) -> None:
        """Paste the newer of ``text`` and the session clipboard at ``position`` and select it.

        Notifies the user when neither holds Haywire nodes.

        Args:
            position: Canvas coordinates for the top-left corner of the pasted nodes.
            text: OS clipboard text; counts only when it is a Haywire clipboard payload.
        """
        x, y = position
        self._handle_canvas_event(UserPasteClipboardEvent(canvasX=x, canvasY=y, clipboardText=text))

    def _own_selection(self) -> tuple[list[str], list[str]]:
        """The session's selected node and edge ids that exist in this canvas's graph."""
        edit = self._session.context.data[EditState]
        nodes = [
            node_id for node_id in edit.selected_nodes if self.graph.get_node_wrapper(node_id) is not None
        ]
        edges = [
            edge_id for edge_id in edit.selected_edges if self.graph.get_edge_wrapper(edge_id) is not None
        ]
        return nodes, edges

    def show_session_selection(self) -> None:
        """Show the session's selection on this canvas, pruned to what it draws.

        The session's selection, active node and active edge are narrowed to the nodes and edges this
        canvas shows, written back to the session and pushed to the browser, and ``SelectionMoved`` is
        published. Nothing the canvas does not show stays selected.
        """
        context = self._session.context
        edit = context.data[EditState]
        nodes = {n for n in edit.selected_nodes if self.visual_layer.shows_node(n)}
        edges = {e for e in edit.selected_edges if self.visual_layer.shows_edge(e)}
        active_node = edit.active_node
        if active_node is not None and active_node.node_id not in nodes:
            active_node = None
        active_edge = edit.active_edge
        if active_edge is not None and active_edge.edge_id not in edges:
            active_edge = None
        self.selection.selected_nodes = nodes
        self.selection.selected_edges = edges
        edit.selected_nodes = nodes
        edit.selected_edges = edges
        edit.active_node = active_node
        edit.active_edge = active_edge
        context.active_component = active_node.registry_key if active_node is not None else None
        self._push_selection()
        self._session.publish(SelectionMoved())

    def _active_payload(self) -> dict[str, str]:
        """Return the session's primary element when this canvas shows it, in the browser's payload form."""
        edit = self._session.context.data[EditState]
        if edit.active_node is not None and edit.active_node.node_id in self.selection.selected_nodes:
            return {"kind": "node", "id": edit.active_node.node_id}
        if edit.active_edge is not None and edit.active_edge.edge_id in self.selection.selected_edges:
            return {"kind": "edge", "id": edit.active_edge.edge_id}
        return {"kind": "", "id": ""}

    def _push_selection(self) -> None:
        self.visual_layer.sync_selections(
            self.selection.selected_nodes, self.selection.selected_edges, active=self._active_payload()
        )

    def _reshow_selection(self) -> None:
        """Send a freshly mounted browser canvas the selection it should show; it starts empty."""
        if self.selection.selected_nodes or self.selection.selected_edges:
            self._push_selection()

    def clear_selection(self) -> None:
        """Empty this canvas's selection, in the browser too. Publishes nothing."""
        self.selection.selected_nodes = set()
        self.selection.selected_edges = set()
        self.visual_layer.sync_selections(set(), set())

    def select_all_toggle(self) -> None:
        """Select every unlocked node, or clear the selection when that is already it."""
        self.selection.select_all_toggle(self.visual_layer.is_locked)

    def clear_all_visuals(self):
        """Clear all visual representations."""
        self.visual_layer.clear_all_visuals()
        self.selection.selected_nodes.clear()
        self.selection.selected_edges.clear()

    # Kept for callers that still reference these directly
    @property
    def node_panels(self) -> Dict:
        return self.visual_layer.node_panels

    @property
    def edge_states(self) -> Dict:
        return self.visual_layer.edge_states

    @property
    def selected_nodes(self) -> Set[str]:
        return self.selection.selected_nodes

    @property
    def selected_edges(self) -> Set[str]:
        return self.selection.selected_edges

    def _has_clipboard_content(self) -> bool:
        clipboard = self._session.context.data[EditState].clipboard
        return clipboard is not None and len(clipboard.payload.get("nodes", {})) > 0

    def cleanup(self):
        """Unsubscribe from graph validation and release resources."""
        logger.info(f"🔧 Shutting down GraphCanvasManager for {self.session_id} ...")

        # Cancel FIRST: a chunked load still running would otherwise keep
        # mounting nodes into a canvas the teardown below is dismantling, and
        # repopulate the node_panels that visual_layer.cleanup() just cleared.
        if self._sync_task is not None and not self._sync_task.done():
            self._sync_task.cancel()
        self._sync_task = None

        try:
            self.graph.unsubscribe_from_validation(self.visual_layer.on_validated)
            self.graph.unsubscribe_from_validation(self._refresh_toolbar_for)
        except Exception as exc:
            logger.warning(f"GraphCanvasManager: unsubscribe error: {exc}")

        for callback in (self._on_node_theme_changed, self._on_edge_default_changed):
            try:
                self.graph.props._unsubscribe(callback)
            except Exception as exc:
                logger.warning(f"GraphCanvasManager: props unsubscribe error: {exc}")

        if self.canvas_vue:
            self.canvas_vue.cleanup()

        if getattr(self, "_toolbar_provider", None) is not None:
            self._toolbar_provider.destroy()

        self.visual_layer.cleanup()

        logger.info(f"🔧 GraphCanvasManager for {self.session_id} is shut down")
