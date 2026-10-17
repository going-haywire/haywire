"""
SelectionHandlers — selection state and clipboard (copy/paste) events.

Owns: selected_nodes, selected_edges, clipboard.
"""

import json
import logging
import traceback
from typing import Any, Callable, Iterable, Optional, Set, Tuple, TYPE_CHECKING

from nicegui import ui

from haywire.core.access import LevelMode
from haywire.core.graph.clipboard import build_clipboard_payload, is_haywire_payload
from haywire.core.node.layout import PATCH, STAGE, LayoutChannel, layout_position_of, position_of
from haywire.core.undo.actions.graph_actions import ClipboardData
from haywire.core.signals import SelectionMoved

from haywire.ui.components.graph.event_definitions import (
    SelectionChangedEvent,
    UserCopySelectedEvent,
    UserPasteClipboardEvent,
    UserRemoveEvent,
)
from haywire.ui.elements import clipboard_script
from ..event_handlers import handles_event
from ....state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.graph.edit_route import EditRoute
    from haywire.core.graph.base import BaseGraph
    from haywire.core.session.session import Session
    from .visual_layer import VisualLayerHandlers

logger = logging.getLogger(__name__)

DUPLICATE_OFFSET = 40.0
"""Distance, in canvas units on both axes, from the selection to its duplicate."""


def copy_selection_event(nodes: Iterable[str], edges: Iterable[str]) -> UserCopySelectedEvent:
    """The copy event for the given node and edge ids."""
    return UserCopySelectedEvent(selectedNodes=list(nodes), selectedEdges=list(edges))


def remove_selection_event(nodes: Iterable[str], edges: Iterable[str]) -> UserRemoveEvent:
    """The removal event for the given node and edge ids."""
    return UserRemoveEvent(nodes=list(nodes), edges=list(edges))


class SelectionHandlers:
    """
    Handle selection and clipboard canvas events.

    Owns the Python-side record of what is currently selected and what is
    held in the session clipboard.
    """

    def __init__(
        self,
        graph: "BaseGraph",
        route: "EditRoute",
        session_id: str,
        session: Optional["Session"] = None,
        visual_layer: Optional["VisualLayerHandlers"] = None,
        channel: LayoutChannel = PATCH,
        patch_viewport_centre: Optional[Callable[[], Optional[Tuple[float, float]]]] = None,
    ):
        self.channel = channel
        self.patch_viewport_centre = patch_viewport_centre
        self.graph = graph
        self.route = route
        self.session_id = session_id
        self._session = session
        self._visual_layer = visual_layer

        self.selected_nodes: Set[str] = set()
        self.selected_edges: Set[str] = set()

    # Selection changes no document, so it is taken in every level mode.
    @handles_event(SelectionChangedEvent, access=LevelMode.VIEW)
    def process_selection_change(self, event: SelectionChangedEvent):
        """Update local selection state and write through to SessionContext.

        The active (primary) element is whatever the canvas marked active on
        the event — a node OR an edge, never both. An empty active id means the
        selection has no primary (bulk/programmatic change), so both active
        pointers are cleared. See the Active axis / Active-promotion glossary
        entries.
        """
        logger.debug(
            f"Selection changed: nodes={event.selectedNodes}, connections={event.selectedEdges}, "
            f"activeNode={event.activeNodeId!r}, activeEdge={event.activeEdgeId!r}"
        )
        self.selected_nodes = set(event.selectedNodes)
        self.selected_edges = set(event.selectedEdges)

        if self._session is None:
            return

        ctx = self._session.context
        active_node = self.graph.get_node_wrapper(event.activeNodeId) if event.activeNodeId else None
        active_edge = self.graph.get_edge_wrapper(event.activeEdgeId) if event.activeEdgeId else None
        edit_state = ctx.data[EditState]
        edit_state.selected_nodes = self.selected_nodes
        edit_state.selected_edges = self.selected_edges
        edit_state.active_node = active_node
        edit_state.active_edge = active_edge
        ctx.active_component = active_node.registry_key if active_node is not None else None

        self._session.publish(SelectionMoved())

    def prune_node(self, node_id: str) -> None:
        """Drop ``node_id`` from the selection (it left this canvas); publishes ``SelectionMoved``.

        Does nothing when the node is not selected here.
        """
        if node_id not in self.selected_nodes:
            return
        self.selected_nodes = self.selected_nodes - {node_id}
        if self._session is None:
            return
        ctx = self._session.context
        edit_state = ctx.data[EditState]
        edit_state.selected_nodes = self.selected_nodes
        active = edit_state.active_node
        if active is not None and active.node_id == node_id:
            edit_state.active_node = None
            ctx.active_component = None
        self._session.publish(SelectionMoved())

    @handles_event(UserCopySelectedEvent)
    def process_copy_selection(self, event: UserCopySelectedEvent):
        """Serialize the selection to a payload; mirror it and write the OS clipboard."""
        logger.info(
            f"📋 Copying {len(event.selectedNodes)} nodes and {len(event.selectedEdges)} connections"
        )
        if self._session is None:
            logger.warning("Copy ignored: no session bound to handler")
            return
        if not event.selectedNodes:
            return
        try:
            payload = build_clipboard_payload(
                self.graph, event.selectedNodes, event.selectedEdges, self.session_id
            )
            self._session.context.data[EditState].clipboard = ClipboardData(
                payload=payload, timestamp=payload["source"]["timestamp"]
            )
            # Write to the OS clipboard as JSON text (cross-process export).
            ui.run_javascript(clipboard_script(json.dumps(payload)))
        except Exception as e:
            logger.error(f"❌ Error during copy operation: {e}")
            ui.notify(f"Copy failed: {e}", type="negative")
            traceback.print_exc()

    def select_all_toggle(self, is_locked: Callable[[str], bool]) -> None:
        """Select every unlocked node, or clear the selection when that is already it.

        Locked nodes are never selected. The result has no active (primary) node
        or edge.
        """
        candidates = {node_id for node_id in self.graph.node_wrappers if not is_locked(node_id)}
        if candidates and self.selected_nodes == candidates:
            self.selected_nodes = set()
        else:
            self.selected_nodes = candidates
        self.selected_edges = set()

        if self._session is not None:
            ctx = self._session.context
            edit_state = ctx.data[EditState]
            edit_state.selected_nodes = self.selected_nodes
            edit_state.selected_edges = self.selected_edges
            edit_state.active_node = None
            edit_state.active_edge = None
            ctx.active_component = None
            self._session.publish(SelectionMoved())
        if self._visual_layer is not None:
            self._visual_layer.sync_selections(self.selected_nodes, self.selected_edges)

    @handles_event(UserPasteClipboardEvent)
    def process_paste_clipboard(self, event: UserPasteClipboardEvent):
        """Paste: pick the newer of OS-clipboard text vs in-process mirror, then paste."""
        if self._session is None:
            logger.warning("Paste ignored: no session bound to handler")
            return
        editor = self.route.editor()
        if editor is None:
            return

        os_payload = None
        if event.clipboardText:
            try:
                parsed = json.loads(event.clipboardText)
                if is_haywire_payload(parsed):
                    os_payload = parsed
            except (ValueError, TypeError):
                os_payload = None

        mirror = self._session.context.data[EditState].clipboard
        mirror_payload = mirror.payload if mirror is not None else None

        # Arbitrate by timestamp: OS clipboard wins if newer (or mirror absent).
        if os_payload is not None and mirror is not None:
            os_ts = os_payload["source"]["timestamp"]
            chosen = os_payload if os_ts >= mirror.timestamp else mirror_payload
        else:
            chosen = os_payload or mirror_payload

        if chosen is None:
            ui.notify("Nothing to paste", type="warning")
            return

        stage_args = {"patch_fallback": self._patch_fallback()} if self.channel.stage else {}
        result = editor.paste_clipboard(chosen, event.canvasX, event.canvasY, self.channel, **stage_args)
        if result is None:
            # Unknown node types do NOT cause failure (they paste as placeholders);
            # None here means an unexpected error.
            ui.notify("Paste failed", type="negative")
            return

        new_node_ids, new_edge_ids = result
        n = len(new_node_ids)
        ui.notify(f"Pasted {n} node{'s' if n != 1 else ''}", type="positive")
        self._select_pasted(new_node_ids, new_edge_ids)

    def duplicate_selection(self, nodes: list[str], edges: list[str]) -> None:
        """Paste a copy of the given nodes ``DUPLICATE_OFFSET`` below and right of them, and select it.

        Edges are copied when both their ends are among ``nodes``. The session
        and OS clipboards keep their content. With no node to copy, or below
        level mode edit, nothing happens.

        Args:
            nodes: Ids of the nodes to duplicate, all in this handler's graph.
            edges: Ids of the edges to duplicate, all in this handler's graph.
        """
        editor = self.route.editor()
        if not nodes or editor is None:
            return
        payload = build_clipboard_payload(self.graph, nodes, edges, self.session_id)
        if not payload["nodes"]:
            return
        patch_anchor = None
        if self.channel.stage:
            origins = [layout_position_of(node, self.channel) for node in payload["nodes"].values()]
            min_x, min_y = self.channel.to_canvas(min(x for x, _ in origins), min(y for _, y in origins))
            # The copy sits DUPLICATE_OFFSET from the originals in the patch too.
            patch_origins = [position_of(node, PATCH) for node in payload["nodes"].values()]
            patch_anchor = (
                min(x for x, _ in patch_origins) + DUPLICATE_OFFSET,
                min(y for _, y in patch_origins) + DUPLICATE_OFFSET,
            )
        else:
            bbox = payload["bounding_box"]
            min_x, min_y = bbox["min_x"], bbox["min_y"]
        stage_args: dict[str, Any]
        if self.channel.stage:
            stage_args = {"patch_anchor": patch_anchor}
        else:
            # On-stage copies sit DUPLICATE_OFFSET from their originals on stage too.
            stage_origins = [
                position_of(node, STAGE)
                for node in payload["nodes"].values()
                if node.get("node_data", {}).get("props", {}).get("values", {}).get("on_stage")
            ]
            stage_args = {}
            if stage_origins:
                stage_args["stage_anchor"] = (
                    min(x for x, _ in stage_origins) + DUPLICATE_OFFSET,
                    min(y for _, y in stage_origins) + DUPLICATE_OFFSET,
                )
        result = editor.paste_clipboard(
            payload, min_x + DUPLICATE_OFFSET, min_y + DUPLICATE_OFFSET, self.channel, **stage_args
        )
        if result is None:
            ui.notify("Duplicate failed", type="negative")
            return
        self._select_pasted(*result)

    # Class default too, so an instance built without __init__ has no patch canvas to ask.
    patch_viewport_centre: Optional[Callable[[], Optional[Tuple[float, float]]]] = None

    def _patch_fallback(self) -> Optional[Tuple[float, float]]:
        """The patch anchor of a paste onto an empty stage, or ``None`` without a patch viewport."""
        if not self.channel.stage or self.patch_viewport_centre is None:
            return None
        return self.patch_viewport_centre()

    def _select_pasted(self, new_node_ids: list[str], new_edge_ids: list[str]) -> None:
        """Make freshly pasted nodes and edges the selection, here, in the session and on the canvas.

        Publishes ``SelectionMoved`` when a session is bound.
        """
        # A single pasted node also becomes the primary (an unambiguous target,
        # like a freshly created one); a multi-node paste is a bulk change and
        # gets no primary — see the Active axis glossary entry.
        self.selected_nodes = set(new_node_ids)
        self.selected_edges = set(new_edge_ids)
        sole_node = self.graph.get_node_wrapper(new_node_ids[0]) if len(new_node_ids) == 1 else None
        if self._session is not None:
            ctx = self._session.context
            edit_state = ctx.data[EditState]
            edit_state.selected_nodes = self.selected_nodes
            edit_state.selected_edges = self.selected_edges
            edit_state.active_node = sole_node
            edit_state.active_edge = None
            ctx.active_component = sole_node.registry_key if sole_node is not None else None
            self._session.publish(SelectionMoved())
        if self._visual_layer is not None:
            active = (
                {"kind": "node", "id": new_node_ids[0]} if sole_node is not None else {"kind": "", "id": ""}
            )
            self._visual_layer.sync_selections(new_node_ids, new_edge_ids, active=active)
