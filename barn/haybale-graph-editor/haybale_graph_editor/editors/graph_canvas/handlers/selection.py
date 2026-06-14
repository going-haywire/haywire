"""
SelectionHandlers — selection state and clipboard (copy/paste) events.

Owns: selected_nodes, selected_edges, clipboard.
"""

import json
import logging
import traceback
from typing import Optional, Set, TYPE_CHECKING

from nicegui import ui

from haywire.core.graph.clipboard import build_clipboard_payload, is_haywire_payload
from haywire.core.undo.actions.graph_actions import ClipboardData
from haywire.core.session.signals import SelectionMoved

from haywire.ui.components.graph.event_definitions import (
    SelectionChangedEvent,
    UserCopySelectedEvent,
    UserPasteClipboardEvent,
)
from ..event_handlers import handles_event
from ....state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.graph.editor import Editor
    from haywire.core.graph.base import BaseGraph
    from haywire.core.session.session import Session
    from .visual_layer import VisualLayerHandlers

logger = logging.getLogger(__name__)


class SelectionHandlers:
    """
    Handle selection and clipboard canvas events.

    Owns the Python-side record of what is currently selected and what is
    held in the session clipboard.
    """

    def __init__(
        self,
        graph: "BaseGraph",
        editor: "Editor",
        session_id: str,
        session: Optional["Session"] = None,
        visual_layer: Optional["VisualLayerHandlers"] = None,
    ):
        self.graph = graph
        self.editor = editor
        self.session_id = session_id
        self._session = session
        self._visual_layer = visual_layer

        self.selected_nodes: Set[str] = set()
        self.selected_edges: Set[str] = set()

    @handles_event(SelectionChangedEvent)
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
            ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(json.dumps(payload))})")
        except Exception as e:
            logger.error(f"❌ Error during copy operation: {e}")
            ui.notify(f"Copy failed: {e}", type="negative")
            traceback.print_exc()

    @handles_event(UserPasteClipboardEvent)
    def process_paste_clipboard(self, event: UserPasteClipboardEvent):
        """Paste: pick the newer of OS-clipboard text vs in-process mirror, then paste."""
        if self._session is None:
            logger.warning("Paste ignored: no session bound to handler")
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

        result = self.editor.paste_clipboard(chosen, event.canvasX, event.canvasY)
        if result is None:
            # Unknown node types do NOT cause failure (they paste as placeholders);
            # None here means an unexpected error.
            ui.notify("Paste failed", type="negative")
            return

        new_node_ids, new_edge_ids = result
        n = len(new_node_ids)
        ui.notify(f"Pasted {n} node{'s' if n != 1 else ''}", type="positive")

        # Auto-select the freshly pasted subgraph so the user can drag it
        # immediately, but with NO primary (a programmatic bulk change clears
        # the active element — see the Active axis glossary entry). Update both
        # the local record and the session EditState, then push to the canvas.
        self.selected_nodes = set(new_node_ids)
        self.selected_edges = set(new_edge_ids)
        if self._session is not None:
            edit_state = self._session.context.data[EditState]
            edit_state.selected_nodes = self.selected_nodes
            edit_state.selected_edges = self.selected_edges
            edit_state.active_node = None
            edit_state.active_edge = None
        if self._visual_layer is not None:
            self._visual_layer.sync_selections(new_node_ids, new_edge_ids, active={"kind": "", "id": ""})
