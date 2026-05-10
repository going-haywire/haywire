"""
SelectionHandlers — selection state and clipboard (copy/paste) events.

Owns: selected_nodes, selected_edges, clipboard.
"""

import logging
import time
import traceback
from typing import Optional, Set, TYPE_CHECKING

from nicegui import ui

from ..event_definitions import (
    SelectionChangedEvent,
    UserCopySelectedEvent,
    UserPasteClipboardEvent,
)
from ..event_handlers import handles_event
from haywire.core.undo.actions.graph_actions import ClipboardData
from haywire.core.session.signals_and_lifecycle import SelectionMoved
from haybale_studio.state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.graph.editor import Editor
    from haywire.core.graph.base import BaseGraph
    from haywire.core.session.session import Session

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
    ):
        self.graph = graph
        self.editor = editor
        self.session_id = session_id
        self._session = session

        self.selected_nodes: Set[str] = set()
        self.selected_edges: Set[str] = set()

    @handles_event(SelectionChangedEvent)
    def process_selection_change(self, event: SelectionChangedEvent):
        """Update local selection state and write through to SessionContext."""
        logger.debug(f"Selection changed: nodes={event.selectedNodes}, connections={event.selectedEdges}")
        self.selected_nodes = set(event.selectedNodes)
        self.selected_edges = set(event.selectedEdges)

        if self._session is None:
            return

        ctx = self._session.context
        active_node = (
            self.graph.get_node_wrapper(next(iter(self.selected_nodes))) if self.selected_nodes else None
        )
        active_edge = (
            self.graph.get_edge_wrapper(next(iter(self.selected_edges))) if self.selected_edges else None
        )
        edit_state = ctx.data[EditState]
        edit_state.selected_nodes.value = self.selected_nodes
        edit_state.selected_edges.value = self.selected_edges
        edit_state.active_node.value = active_node
        edit_state.active_edge.value = active_edge

        self._session.signal(SelectionMoved())

    @handles_event(UserCopySelectedEvent)
    def process_copy_selection(self, event: UserCopySelectedEvent):
        """Store selected elements in the session clipboard."""
        logger.info(
            f"📋 Copying {len(event.selectedNodes)} nodes and {len(event.selectedEdges)} connections"
        )
        if self._session is None:
            logger.warning("Copy ignored: no session bound to handler")
            return
        try:
            bounding_box = self._calculate_selection_bounds(event.selectedNodes)
            self._session.context.data[EditState].clipboard.value = ClipboardData(
                nodes=event.selectedNodes,
                edges=event.selectedEdges,
                original_to_new_ids={},
                bounding_box=bounding_box,
                timestamp=time.time(),
                source_session_id=self.session_id,
            )
        except Exception as e:
            logger.error(f"❌ Error during copy operation: {e}")
            ui.notify(f"Copy failed: {e}", type="negative")
            traceback.print_exc()

    @handles_event(UserPasteClipboardEvent)
    def process_paste_clipboard(self, event: UserPasteClipboardEvent):
        """Paste clipboard contents — full implementation pending."""
        if self._session is None:
            logger.warning("Paste ignored: no session bound to handler")
            return

        clipboard = self._session.context.data[EditState].clipboard.value
        if not clipboard:
            logger.warning("❌ No clipboard content to paste")
            ui.notify("Nothing to paste", type="warning")
            return

        logger.info(
            f"📄 Pasting {len(clipboard.nodes)} nodes and "
            f"{len(clipboard.edges)} connections "
            f"at ({event.canvasX}, {event.canvasY})"
        )
        # Full paste implementation: editor.paste(clipboard, x, y) — pending

    # -------------------------------------------------------------------------

    def _calculate_selection_bounds(self, node_ids) -> dict:
        """Calculate bounding box of the given node IDs."""
        if not node_ids:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0}

        positions: list[tuple[float, float]] = []
        for node_id in node_ids:
            wrapper = self.graph.get_node_wrapper(node_id)
            if wrapper and wrapper.node:
                positions.append((wrapper.node.props.posX, wrapper.node.props.posY))

        if not positions:
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0}

        return {
            "min_x": min(p[0] for p in positions),
            "min_y": min(p[1] for p in positions),
            "max_x": max(p[0] for p in positions),
            "max_y": max(p[1] for p in positions),
        }
