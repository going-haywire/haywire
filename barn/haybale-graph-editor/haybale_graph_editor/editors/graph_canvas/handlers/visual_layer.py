"""
VisualLayerHandlers — node/edge visual registry and graph-sync events.

Owns: node_panels, edge_states.
Responsible for:
- Translating ValidationResult into add/remove/update visual calls
- Managing the Python-side registry of UINode objects and edge visual states
- Emitting sync events to the Vue canvas component

Edges are emitted in ONE batched ``SyncAllEdgesEvent`` per validation pass, not
one message per edge. Each server->client message costs the client roughly
0.15 ms per mounted node regardless of payload size, so a per-edge message made
opening a graph O(nodes x edges): 672 edges on a 128-node graph took 18.9 s to
reach the screen, against 184 ms for the same edges delivered in one message.
"""

import asyncio
import logging
import time
import traceback
from typing import Callable, Dict, Optional, Tuple, TYPE_CHECKING

from nicegui import ui

from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.core.graph.types import ChangeReason, ValidationResult
from haywire.core.node import BaseNode

from haywire.ui.components.graph.event_definitions import (
    UserRemoveEvent,
    NodesMeasuredEvent,
    NodeCreateRequestEvent,
    SplitEdgeWithRerouteEvent,
    DissolveRerouteEvent,
    EdgeCreatedEvent,
    ElementRedrawEvent,
    ElementResetEvent,
    ElementRevalidateEvent,
    SyncNodePositionEvent,
    SyncNodeRemovalEvent,
    SyncEdgeRemovalEvent,
    SyncAllEdgesEvent,
    SyncSelectionsEvent,
    SyncCanvasClearEvent,
    SyncEdgeReconnectEvent,
    SyncEdgeConnectCancelEvent,
)

from ..event_handlers import handles_event
from ..ui_node import UINode
from ..ui_edge import EdgeVisualState, edge_sync_payload, edge_visual_state
from ....state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.graph.editor import Editor
    from haywire.core.graph.base import BaseGraph
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.ui.skin.factory import SkinFactory
    from haywire.ui.components.graph.canvas import GraphCanvasVue
    from haywire.core.session.context import SessionContext

logger = logging.getLogger(__name__)


def summarize_compatibility(node_warning_count: int, library_messages: list[str]) -> str | None:
    """Build the on-open compatibility summary text, or None if nothing to report.

    Pure/UI-free so it is unit-testable. Library-wide messages are listed
    verbatim; per-node warnings are summarised as a count (the badges carry
    the detail per node).
    """
    if node_warning_count == 0 and not library_messages:
        return None
    parts: list[str] = []
    if node_warning_count:
        noun = "node" if node_warning_count == 1 else "nodes"
        parts.append(
            f"{node_warning_count} {noun} were saved with an older library "
            f"version and may not reflect later changes (see the warning badges)."
        )
    parts.extend(library_messages)
    return " ".join(parts)


class VisualLayerHandlers:
    """
    Manage the Python-side visual registry for the graph canvas.

    Owns node_panels and edge_states, and keeps them in sync with the graph
    by processing ValidationResult objects from the graph's validation callback.
    """

    def __init__(
        self,
        graph: "BaseGraph",
        editor: "Editor",
        skin_factory: "SkinFactory",
        canvas_vue: "GraphCanvasVue",
        context: Optional["SessionContext"] = None,
    ):
        self.graph = graph
        self.editor = editor
        self.skin_factory = skin_factory
        self.canvas_vue = canvas_vue
        self.context = context

        self.node_panels: Dict[str, UINode] = {}
        # Last visual state emitted per edge. Doubles as the "is this edge
        # already drawn?" registry — membership, not the value, is what
        # ``on_validated`` and ``process_start_reconnect`` test.
        self.edge_states: Dict[str, EdgeVisualState] = {}

    # -------------------------------------------------------------------------
    # Graph sync
    # -------------------------------------------------------------------------

    def on_validated(self, result: ValidationResult):
        """
        Handle validation results and update visual layer accordingly.

        Processes node and edge change reasons, delegating to the appropriate
        add/remove/refresh methods.
        """
        logger.info(f"🔄 Validation: {result.total_changes} changes in {result.validation_time_ms:.2f}ms")

        if result.canvas_size is not None:
            self._apply_canvas_resize(*result.canvas_size)

        for node_id, reason in result.nodes.items():
            if reason == ChangeReason.NODE_ADDED:
                node_wrapper = self.graph.get_node_wrapper(node_id)
                if node_wrapper and node_id not in self.node_panels:
                    position = (node_wrapper.node.props.posX, node_wrapper.node.props.posY)
                    self.add_node_visual(node_wrapper.node, position)
                    logger.debug(f"  + Added node UI: {node_id}")

            elif reason == ChangeReason.NODE_REMOVED:
                if node_id in self.node_panels:
                    self.remove_node_visual(node_id)
                    logger.debug(f"  - Removed node UI: {node_id}")

            elif reason == ChangeReason.NODE_MOVED:
                ui_node = self.node_panels.get(node_id)
                if ui_node:
                    moved_wrapper = self.graph.get_node_wrapper(node_id)
                    if moved_wrapper:
                        new_position = (moved_wrapper.node.props.posX, moved_wrapper.node.props.posY)
                        self.update_node_position(node_id, new_position)
                        logger.debug(f"  ↔ Moved node: {node_id}")

            elif reason.requires_redraw():
                ui_node = self.node_panels.get(node_id)
                if ui_node:
                    self.refresh_node_visual(ui_node, reason)
                    logger.debug(f"  🔄 Redrawn node: {node_id} ({reason.value})")

        # Adds and redraws collect into one batch; removals stay per-edge
        # (they are rare, and a removal carries no payload worth batching).
        batch: list[dict] = []

        for edge_uuid, reason in result.edges.items():
            if reason == ChangeReason.EDGE_ADDED:
                edge_wrapper = self.graph.get_edge_wrapper(edge_uuid)
                if edge_wrapper and edge_uuid not in self.edge_states:
                    batch.append(self._register_edge_visual(edge_wrapper))
                    logger.debug(f"  + Added edge UI: {edge_uuid}")

            elif reason == ChangeReason.EDGE_REMOVED:
                if edge_uuid in self.edge_states:
                    self.remove_edge_visual(edge_uuid)
                    logger.debug(f"  - Removed edge UI: {edge_uuid}")

            elif reason.requires_redraw():
                payload = self._refresh_edge_visual(edge_uuid)
                if payload is not None:
                    batch.append(payload)
                    logger.debug(f"  🔄 Redrawn edge: {edge_uuid} ({reason.value})")

        if batch:
            self.canvas_vue.emit_sync_event(SyncAllEdgesEvent(edges=batch))

        self.canvas_vue.update()

    def sync_with_graph(self):
        """Synthesise a full-add ValidationResult and process it via on_validated.

        Synchronous: the whole graph is mounted inside one call, blocking the
        event loop for its duration. for a large graphs
        (>=``CHUNKED_LOAD_THRESHOLD`` nodes) — see :meth:`sync_with_graph_chunked`
        """
        node_count = len(self.graph.node_wrappers)
        edge_count = len(self.graph.edge_wrappers)
        logger.info(f"🔄 Initial sync: {node_count} nodes, {edge_count} edges")
        try:
            # Measure the full node/edge render (on_validated → per-node
            # UINode.render via add_node_visual). This is the Python-side cost of
            # selecting/opening a graph; browser-side Vue mount is not included.
            render_t0 = time.perf_counter()
            self.on_validated(self._full_add_result())
            self._log_render_cost(render_t0, node_count, edge_count)
            self._notify_compatibility()
        except Exception as e:
            logger.error(f"❌ Error during initial sync: {e}")
            traceback.print_exc()

    async def sync_with_graph_chunked(
        self,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_phase: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Mount the graph a node at a time, yielding to the event loop between.

        Same end state as :meth:`sync_with_graph` — identical element tree — but
        the node mounts are interleaved with ``await asyncio.sleep(0)`` so the
        server keeps serving everyone else while a large graph opens.

        Edges are NOT chunked: they already go out as a single batched
        ``SyncAllEdgesEvent``, so there is nothing to interleave. To the contrary,
        a chuncked edge batch would be a performance regression: after every
        chunck the vue component tree walk would be er-run.

        Cancellation: the caller's task is cancelled by
        :meth:`GraphCanvasManager.cleanup` when the editor closes mid-load.
        ``CancelledError` propagates untouched — a half-built canvas is being
        torn down anyway, and ``cleanup`` clears ``node_panels`` after.

        Args:
            on_progress: Called after each node as ``(mounted, total)``, for the
                load overlay's readout. Runs inside the loop, so it must stay
                cheap — anything slow here is paid once per node.
            on_phase: Called once with a status line when the load moves off
                per-node mounting and onto the edge batch.
        """
        node_count = len(self.graph.node_wrappers)
        edge_count = len(self.graph.edge_wrappers)
        logger.info(f"🔄 Initial sync (chunked): {node_count} nodes, {edge_count} edges")
        try:
            render_t0 = time.perf_counter()

            # Snapshot the wrappers: the loop awaits, so the graph's own dict
            # could be mutated under us by an event that lands mid-load.
            for index, wrapper in enumerate(list(self.graph.node_wrappers.values()), start=1):
                node = wrapper.node
                if node.node_id not in self.node_panels:
                    self.add_node_visual(node, (node.props.posX, node.props.posY))
                if on_progress is not None:
                    on_progress(index, node_count)
                await asyncio.sleep(0)

            # Edges + canvas resize + the batched sync event, in one pass. Node
            # entries are omitted: they are mounted above, and on_validated
            # skips any node already in node_panels anyway.
            if on_phase is not None and edge_count:
                # Nodes are done; what remains is the edge batch reaching the
                # browser. Say so rather than sitting on "200 / 200".
                on_phase(f"Drawing {edge_count} edges…")

            self.on_validated(self._full_add_result(include_nodes=False))

            await self._await_client_drawn(edge_count)

            self._log_render_cost(render_t0, node_count, edge_count, chunked=True)
            self._notify_compatibility()
        except asyncio.CancelledError:
            logger.info("🔄 Chunked sync cancelled (editor closed mid-load)")
            raise
        except Exception as e:
            logger.error(f"❌ Error during chunked initial sync: {e}")
            traceback.print_exc()

    async def _await_client_drawn(self, edge_count: int) -> None:
        """Block until the browser has actually drawn the edges just emitted.

        ``emit_sync_event`` is fire-and-forget: ``run_method`` queues a message
        in the client outbox and returns, so the Python loop finishes with the
        edge batch still in flight. Releasing the load overlay there hands back
        a canvas with every node drawn and NOT ONE EDGE — measured on a
        100-node/198-edge graph: 0 edge paths at the moment of unlock, all 198
        about a second later.

        An awaited ``run_javascript`` fixes the ordering rather than guessing at
        a delay: it is queued behind the edge message and the outbox is FIFO, so
        its reply cannot come back until the client has processed the batch.

        Drawing then continues across several frames — ``_syncAllEdges`` hands
        its geometry pass to ``_updateEdgesChunked``, which slices the work so a
        big batch cannot block the main thread past socket.io's ping timeout. So
        the script waits for the edge paths to actually be in the DOM rather
        than for a fixed number of frames, and gives up on its own deadline well
        inside the ``timeout`` below.

        Best-effort by design. A timeout, a disconnected browser, or a test
        without a real client must not strand the user behind an overlay that
        has no dismiss button, so every failure just returns and lets the load
        finish.
        """
        if not edge_count:
            return
        client = getattr(self.canvas_vue, "client", None)
        if client is None:
            try:
                client = ui.context.client
            except Exception as exc:
                logger.debug(f"VisualLayer: no client to confirm edge draw ({exc})")
                return
        script = f"""
            const want = {edge_count};
            const svg = document.getElementById('connection-svg');
            const drawn = () => svg
                ? svg.querySelectorAll('path[data-edge-id]').length / 2
                : 0;
            const deadline = performance.now() + 20000;
            while (drawn() < want && performance.now() < deadline) {{
                await new Promise(r => requestAnimationFrame(r));
            }}
            // One more frame so the last slice's paths are laid out, not just present.
            await new Promise(r => requestAnimationFrame(r));
            return drawn();
        """
        try:
            await client.run_javascript(script, timeout=25.0)
        except Exception as exc:
            logger.debug(f"VisualLayer: edge-draw confirmation skipped ({exc})")

    # -- shared scaffolding for the two sync paths ----------------------------

    def _full_add_result(self, *, include_nodes: bool = True) -> ValidationResult:
        """Synthesise the "everything was just added" result the sync paths process."""
        return ValidationResult(
            nodes=(
                {node_id: ChangeReason.NODE_ADDED for node_id in self.graph.node_wrappers.keys()}
                if include_nodes
                else {}
            ),
            edges={edge_uuid: ChangeReason.EDGE_ADDED for edge_uuid in self.graph.edge_wrappers.keys()},
            canvas_size=(self.graph.canvas_width, self.graph.canvas_height),
            validation_time_ms=0.0,
        )

    def _log_render_cost(
        self, render_t0: float, node_count: int, edge_count: int, *, chunked: bool = False
    ) -> None:
        render_ms = (time.perf_counter() - render_t0) * 1000.0
        per_node = render_ms / node_count if node_count else 0.0
        how = " (chunked)" if chunked else ""
        logger.info(
            f"⏱️ Graph render{how}: {render_ms:.1f} ms for {node_count} nodes "
            f"({per_node:.2f} ms/node), {edge_count} edges"
        )
        logger.info("✅ Initial sync completed via validation pipeline")

    def _notify_compatibility(self) -> None:
        """One-time compatibility summary for this load."""
        node_warning_count = sum(1 for w in self.graph.node_wrappers.values() if w.state.has_warning())
        library_messages = list(getattr(self.graph, "library_compatibility_findings", []))
        summary = summarize_compatibility(node_warning_count, library_messages)
        if summary:
            ui.notify(summary, type="warning", multi_line=True, timeout=0, close_button=True)

    # -------------------------------------------------------------------------
    # Canvas resize
    # -------------------------------------------------------------------------

    def _apply_canvas_resize(self, width: int, height: int) -> None:
        """Push new canvas dimensions to canvas_vue and its zoom viewport."""
        logger.debug(f"🖼️ Canvas resize → {width}×{height}")
        if self.canvas_vue:
            self.canvas_vue.set_canvas_size(width, height)
            zoom_container = getattr(self.canvas_vue, "zoom_container", None)
            if zoom_container:
                zoom_container.set_canvas_size(width, height)

    # -------------------------------------------------------------------------
    # Node visual management
    # -------------------------------------------------------------------------

    def add_node_visual(self, node: BaseNode, position: Tuple[float, float] = (100, 100)) -> bool:
        """Create and register a UINode for the given node.

        Idempotent per node id, mirroring ``remove_node_visual``'s guard.
        Overwriting ``node_panels[node_id]`` would drop only the PYTHON
        reference — the first UINode's container stays mounted in
        ``canvas_vue``, orphaning a card that duplicates its ``data-node-id``
        and every pin uuid, so ``getElementById`` resolves edges to whichever
        copy comes first.

        Warns rather than returning quietly: a second add is not expected,
        since ``sync_with_graph`` already synthesises NODE_ADDED for every node.
        """
        x, y = position
        node_id = node.node_id
        logger.debug(f"Adding node visual for {node_id} at position ({x}, {y})")

        existing = self.node_panels.get(node_id)
        if existing is not None:
            logger.warning(
                f"⚠️ Node visual for {node_id} already exists; refreshing in place "
                "rather than mounting a duplicate"
            )
            self.refresh_node_visual(existing, ChangeReason.NODE_ADDED)
            return True

        wrapper = self.graph.get_node_wrapper(node_id)
        if not wrapper:
            logger.warning(f"⚠️ ERROR: No wrapper found for node {node_id}, hot reload won't work")
            return False

        with self.canvas_vue:
            with (
                ui.element("div")
                .classes("absolute")
                .style(f"left: {x}px; top: {y}px; z-index: 100; transform-origin: top-left; cursor: move;")
                .props(f'id="{node_id}" data-node-id="{node_id}" ') as container
            ):
                ui_node = UINode(container, wrapper, self.skin_factory)
                ui_node.register_sync_event_emitter(self.canvas_vue.emit_sync_event)
                ui_node.refresh(ChangeReason.NODE_ADDED)
                ui_node.position = position
                self.node_panels[node_id] = ui_node

        logger.debug(f"Successfully added node visual for {node_id}")
        return True

    def refresh_node_visual(self, ui_node: UINode, reason: ChangeReason) -> None:
        """Refresh a node's visual representation."""
        ui_node.refresh(reason)

    def remove_node_visual(self, node_id: str) -> bool:
        """Remove a node's visual representation and any connected edge visuals."""
        if node_id not in self.node_panels:
            return False

        edges_to_remove = [
            edge_id
            for edge_id, wrapper in self.graph.edge_wrappers.items()
            if wrapper.sink_node_id == node_id or wrapper.source_node_id == node_id
        ]
        for edge_id in edges_to_remove:
            self.remove_edge_visual(edge_id)

        ui_node = self.node_panels.pop(node_id)
        ui_node.delete()
        self.canvas_vue.emit_sync_event(SyncNodeRemovalEvent(nodeId=node_id))
        return True

    def remove_all_node_visuals(self):
        """Remove all node visuals."""
        for node_id in list(self.node_panels.keys()):
            self.remove_node_visual(node_id)

    def update_node_position(self, node_id: str, position: Tuple[float, float]):
        """Update a node's visual position and emit a sync event."""
        if node_id not in self.node_panels:
            return

        x, y = position
        container = self.node_panels[node_id].container
        container.style(f"left: {x}px; top: {y}px; z-index: 100;")
        container.update()
        self.node_panels[node_id].position = position

        sync_event = SyncNodePositionEvent(nodeId=node_id, position={"x": x, "y": y})
        self.canvas_vue.emit_sync_event(sync_event)

    # -------------------------------------------------------------------------
    # Edge visual management
    # -------------------------------------------------------------------------

    def _register_edge_visual(self, edge_wrapper: EdgeWrapper) -> dict:
        """Record an edge's visual state and return its sync payload.

        Registers only — the caller batches the returned payload into the
        pass's single ``SyncAllEdgesEvent``.
        """
        edge_id = edge_wrapper.edge_id
        logger.debug(
            f"🔗 Creating edge visual: "
            f"{edge_wrapper.source_node_id}:{edge_wrapper.outlet_port_id} -> "
            f"{edge_wrapper.sink_node_id}:{edge_wrapper.inlet_port_id}"
        )
        state = edge_visual_state(edge_wrapper)
        self.edge_states[edge_id] = state
        return edge_sync_payload(edge_wrapper, state)

    def _refresh_edge_visual(self, edge_id: str) -> Optional[dict]:
        """Re-run the visual policy for a drawn edge; payload only if it changed.

        The unchanged case is the common one — a validation pass marks many
        edges for redraw whose stroke values are identical — so returning None
        here is what keeps the batch small.
        """
        if edge_id not in self.edge_states:
            return None
        edge_wrapper = self.graph.get_edge_wrapper(edge_id)
        if edge_wrapper is None:
            return None

        state = edge_visual_state(edge_wrapper)
        if state == self.edge_states[edge_id]:
            return None

        self.edge_states[edge_id] = state
        return edge_sync_payload(edge_wrapper, state)

    def add_edge_visual(self, edge_wrapper: EdgeWrapper) -> bool:
        """Register an edge visual and sync it on its own.

        The single-edge path, for callers outside the validation pass; the
        pass itself batches through ``_register_edge_visual``.
        """
        payload = self._register_edge_visual(edge_wrapper)
        self.canvas_vue.emit_sync_event(SyncAllEdgesEvent(edges=[payload]))
        return True

    def remove_edge_visual(self, edge_id: str) -> bool:
        """Remove an edge's visual representation."""
        if edge_id not in self.edge_states:
            return False

        del self.edge_states[edge_id]

        sync_event = SyncEdgeRemovalEvent(edge_id=edge_id)
        self.canvas_vue.emit_sync_event(sync_event)
        logger.debug(f"🔗 Removed edge visual: {edge_id}")
        return True

    def remove_all_edge_visuals(self):
        """Remove all edge visuals."""
        for edge_id in list(self.edge_states.keys()):
            self.remove_edge_visual(edge_id)

    # -------------------------------------------------------------------------
    # Selection + full clear
    # -------------------------------------------------------------------------

    def sync_selections(self, selected_nodes, selected_edges, active=None):
        """Emit consolidated selection sync event to Vue.

        ``active`` is the single primary element to reconcile on the canvas:
        ``{"kind": "node"|"edge"|"", "id": str}``. ``None`` (the default) means
        "no primary" and is sent as the ``{"kind": "", "id": ""}`` sentinel,
        clearing any active highlight.
        """
        if active is None:
            active = {"kind": "", "id": ""}
        sync_event = SyncSelectionsEvent(
            nodes=list(selected_nodes),
            edges=list(selected_edges),
            active=active,
        )
        self.canvas_vue.emit_sync_event(sync_event)

    def _make_sole_active_node(self, wrapper: "NodeWrapper") -> None:
        """Make ``wrapper`` the whole selection, and its active (primary) element.

        A freshly created node is a single-element, user-initiated change, so it
        gets a primary — unlike a bulk paste, which selects without one (see the
        Active axis / Active-promotion glossary entries). Writes EditState first,
        then pushes the same state to the canvas so both sides agree.
        """
        if self.context is None:
            return
        node_id = wrapper.node_id
        edit_state = self.context.data[EditState]
        edit_state.selected_nodes = {node_id}
        edit_state.selected_edges = set()
        edit_state.active_node = wrapper
        edit_state.active_edge = None
        self.context.active_component = wrapper.registry_key
        self.sync_selections([node_id], [], active={"kind": "node", "id": node_id})

    def clear_all_visuals(self):
        """Clear all visual representations and notify Vue."""
        self.remove_all_edge_visuals()
        self.remove_all_node_visuals()
        self.canvas_vue.emit_sync_event(SyncCanvasClearEvent())

    def cleanup(self):
        """Bulk-teardown path for full canvas close.

        Drops each node's Haywire-side subscriptions (no per-node DOM delete —
        the owning container's clear/delete removes all node DOM in one batch)
        and clears edge state without emitting per-edge sync events. Use
        ``remove_node_visual`` / ``remove_edge_visual`` for in-session
        single-element removal, which do delete DOM / emit sync.
        """
        for ui_node in self.node_panels.values():
            try:
                ui_node.teardown_subscriptions()
            except Exception as exc:
                logger.warning(f"VisualLayer.cleanup: node teardown error: {exc}")
        self.node_panels.clear()

        # Edge visuals hold no subscriptions and no DOM of their own — the
        # canvas clear removes their SVG paths — so dropping the states is the
        # whole teardown.
        self.edge_states.clear()

    # -------------------------------------------------------------------------
    # Event handlers — graph mutation requests
    # -------------------------------------------------------------------------

    @handles_event(NodesMeasuredEvent)
    def process_nodes_measured(self, event: NodesMeasuredEvent):
        """Write one frame's measured auto-axis sizes back into node props.

        The ResizeObserver (see UINode._attach_size_observer) reports
        offsetWidth/offsetHeight for AUTO axes only; a manual axis is omitted
        (``None``) so measurement never clobbers a user-fixed size. The client
        rAF-batches a frame's measurements into a single event — a large graph
        fires every node's observer in one layout pass, and a message per node
        made 200+ node graphs unusable.

        Each write goes straight to ``props`` (NOT through the editor) so it is
        not undoable and does not trigger a card redraw — it lands on the size
        subscriber (UINode._on_size_field_change), which only restyles the
        slot. Epsilon-gated ~1px so sub-pixel jitter doesn't churn props; the
        client applies the same epsilon so unchanged sizes never reach here.
        """
        for measurement in event.measurements:
            node_id = measurement.get("nodeId")
            if node_id is None:
                continue
            ui_node = self.node_panels.get(node_id)
            if ui_node is None:
                continue
            props = ui_node.wrapper.node.props
            width = measurement.get("width")
            height = measurement.get("height")
            if width is not None and abs(width - props.width) > 1.0:
                props.width = float(width)
            if height is not None and abs(height - props.height) > 1.0:
                props.height = float(height)

    def _is_locked(self, node_id: str) -> bool:
        """True when the node exists and carries ``props.locked``."""
        wrapper = self.graph.get_node_wrapper(node_id)
        if wrapper is None:
            return False
        return bool(wrapper.node.props.locked)

    @handles_event(UserRemoveEvent)
    def process_element_removal(self, event: UserRemoveEvent):
        """Handle unified element removal, skipping locked nodes.

        The primary guard is upstream, in the selection model: canvas.vue keeps
        a locked node out of any multi-selection, so the usual delete never
        carries one. What reaches here is the case that survives that rule — a
        locked node selected ALONE (which stays possible, since its properties
        panel is the only way to unlock it) and then deleted.

        Kept as a filter rather than a veto so the shape holds whatever the
        selection model does later, and the skip is REPORTED either way: a
        silent skip is the failure mode where the user assumes it worked.

        Only the node is protected; its edges are not. An edge belongs to two
        nodes, so letting one veto operations on its neighbour would surprise in
        the other direction (see the locked-node design, ADR 0032's successor
        notes in properties.py).
        """
        nodes = [n for n in event.nodes if not self._is_locked(n)]
        skipped = len(event.nodes) - len(nodes)

        if not nodes and not event.edges:
            if skipped:
                ui.notify(f"{skipped} locked node(s) — nothing deleted", type="warning")
            return

        total = len(nodes) + len(event.edges)
        logger.info(f"🗑️ Removing {total} elements: {len(nodes)} nodes, {len(event.edges)} connections")
        if self.editor.remove_elements(nodes, event.edges):
            msg = f"Deleted {total} element(s)"
            if skipped:
                msg += f" — {skipped} locked node(s) skipped"
            ui.notify(msg, type="positive")
        else:
            ui.notify("Failed to delete elements", type="warning")

    @handles_event(NodeCreateRequestEvent)
    def process_node_creation_request(self, event: NodeCreateRequestEvent):
        """Handle node creation requests."""
        logger.info(
            f"📝 Creating node: {event.registryKey} at ({event.position['x']}, {event.position['y']})"
        )
        try:
            wrapper = self.editor.create_wrapper(
                event.registryKey,
                (event.position["x"], event.position["y"]),
            )
            if wrapper:
                ui.notify(f"Created {event.registryKey} node", type="positive")
                if event.pending_connection:
                    self._try_auto_wire(wrapper, event.pending_connection)
                self._make_sole_active_node(wrapper)
            else:
                ui.notify(f"Failed to create node of type: {event.registryKey}", type="negative")
        except Exception as e:
            logger.error(f"Error creating node: {e}")
            ui.notify(f"Error creating node: {e}", type="negative")

    @handles_event(SplitEdgeWithRerouteEvent)
    def process_split_edge_with_reroute(self, event: SplitEdgeWithRerouteEvent):
        """Split a data edge and insert a reroute node (one undoable op).

        The reroute node type is discovered via the registry's ``_is_reroute``
        flag so this handler carries no import dependency on any concrete
        reroute implementation.
        """
        reroute_cls = self.editor._node_factory.get_reroute_node()
        if reroute_cls is None:
            ui.notify("No reroute node available", type="negative")
            return

        logger.info(f"✂️ Splitting edge {event.edge_id} with reroute")
        try:
            reroute_id = self.editor.split_edge_with_reroute(
                event.edge_id,
                (event.position["x"], event.position["y"]),
                registry_key=reroute_cls.class_identity.registry_key,
            )
            if reroute_id:
                ui.notify("Inserted reroute", type="positive")
            else:
                ui.notify("Failed to insert reroute", type="negative")
        except Exception as e:
            logger.error(f"Error splitting edge with reroute: {e}")
            ui.notify(f"Error inserting reroute: {e}", type="negative")

    @handles_event(DissolveRerouteEvent)
    def process_dissolve_reroute(self, event: DissolveRerouteEvent):
        """Dissolve a reroute node (one undoable op)."""
        logger.info(f"🔗 Dissolving reroute {event.node_id}")
        if self.editor.dissolve_reroute(event.node_id):
            ui.notify("Dissolved reroute", type="positive")
        else:
            ui.notify("Failed to dissolve reroute", type="negative")

    def _try_auto_wire(self, wrapper, pending: dict) -> None:
        """
        After node creation from a mid-drag context menu, auto-wire the new
        node to a compatible port on the dragged-from pin's side.

        ``pending`` carries the dragged-from pin's metadata (pin_id, node_id,
        pin_dir, flow_type, data_type) — see NodeCreateRequestEvent.

        TODO: Static port-type introspection (before instantiation) is not yet supported.
        """
        if self.context is None:
            return

        pending_pin_dir = pending.get("pin_dir", "")  # 'inlet' or 'outlet'
        pending_flow = pending.get("flow_type", "")
        pending_data = pending.get("data_type", "")
        pending_node_id = pending.get("node_id", "")
        pending_pin_id = pending.get("pin_id", "")

        # The new node's compatible direction is the opposite of the dragged pin.
        target_dir = "inlet" if pending_pin_dir == "outlet" else "outlet"

        compatible_ports = []
        for port_id, port in wrapper.node.ports.items():
            if target_dir == "inlet" and not port.is_inlet():
                continue
            if target_dir == "outlet" and not port.is_outlet():
                continue
            # Flow type must match (pending_flow is the .value string, e.g. 'data', 'control')
            if pending_flow and port.flow_type.value != pending_flow:
                continue
            # For data pins, data type must match if provided
            if pending_data:
                type_key = port.stored_type.class_identity.registry_key
                if type_key != pending_data:
                    continue
            compatible_ports.append(port_id)

        if not compatible_ports:
            logger.debug(
                f"Auto-wire: {len(compatible_ports)} compatible typed ports on {wrapper.node_id}, "
                f"connecting to ghost pin (edge will be unlinked)"
            )
            # No exact match — connect to the ghost pin. The graph will create an
            # unlinked/invalid edge that draws to the ghost pin via the fallback mechanism.
            target_port_id = "root_in" if target_dir == "inlet" else "root_out"
        else:
            target_port_id = compatible_ports[0]
        new_node_id = wrapper.node_id

        if pending_pin_dir == "outlet":
            # dragged from outlet → new node inlet
            success = self.editor.create_edge(pending_node_id, pending_pin_id, new_node_id, target_port_id)
        else:
            # dragged from inlet → new node outlet
            success = self.editor.create_edge(new_node_id, target_port_id, pending_node_id, pending_pin_id)

        if success:
            logger.info(f"Auto-wired {pending_node_id}:{pending_pin_id} → {new_node_id}:{target_port_id}")
            self.canvas_vue.emit_sync_event(SyncEdgeConnectCancelEvent())
        else:
            logger.warning(
                f"Auto-wire failed for {pending_node_id}:{pending_pin_id} → {new_node_id}:{target_port_id}"
            )

    @handles_event(EdgeCreatedEvent)
    def process_edge_creation(self, event: EdgeCreatedEvent):
        """Handle connection creation."""
        logger.debug(
            f"Creating connection: {event.sourceNodeId}:{event.outletPinId} -> "
            f"{event.sinkNodeId}:{event.inletPinId}"
        )
        if self.editor.create_edge(
            event.sourceNodeId,
            event.outletPinId,
            event.sinkNodeId,
            event.inletPinId,
        ):
            ui.notify("Connection created")
        else:
            ui.notify("Failed to create connection", type="negative")

    @handles_event(ElementRedrawEvent, ElementResetEvent, ElementRevalidateEvent)
    def process_update_element(self, event):
        """Forward element update requests directly to the graph."""
        if isinstance(event, ElementRedrawEvent):
            for node_id in event.nodes:
                self.graph.request_node_redraw(node_id)
            for edge_id in event.edges:
                self.graph.request_edge_redraw(edge_id)

        elif isinstance(event, ElementRevalidateEvent):
            for node_id in event.nodes:
                self.graph.request_node_revalidation(node_id)
            for edge_id in event.edges:
                self.graph.request_edge_revalidation(edge_id)

        elif isinstance(event, ElementResetEvent):
            for node_id in event.nodes:
                self.graph.request_node_reset(node_id)
            for edge_id in event.edges:
                self.graph.request_edge_reset(edge_id)

    @handles_event(SyncEdgeReconnectEvent)
    def process_start_reconnect(self, event: SyncEdgeReconnectEvent):
        """Forward reconnect command to Vue, then remove the edge from the graph.

        Order matters:
        1. Pre-remove the edge from edge_states so that the validation callback fired
           by editor.remove_elements does not emit a redundant syncEdgeRemoval to Vue.
        2. Send syncEdgeReconnect to Vue — it removes the edge visual and starts the
           click-click drag from the anchor pin.
        3. Remove the edge from the graph so a subsequent edgeCreated for the same
           pins is not rejected as a duplicate.
        """
        self.edge_states.pop(event.edge_id, None)
        self.canvas_vue.emit_sync_event(event)
        self.editor.remove_elements([], [event.edge_id])
