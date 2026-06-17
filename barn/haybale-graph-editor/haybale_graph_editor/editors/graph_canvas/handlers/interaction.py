"""
InteractionHandlers — drag and edge-click event handlers.

Stateless: all mutations are delegated to Editor, which records undo actions
internally.  Undo grouping is achieved by the fence pair on drag start/end.
"""

import logging
from typing import TYPE_CHECKING

from haywire.ui.components.graph.event_definitions import (
    UserDragStartEvent,
    UserDragUpdateEvent,
    UserDragEndEvent,
    EdgeClickedEvent,
)
from ..event_handlers import handles_event

if TYPE_CHECKING:
    from haywire.core.graph.editor import Editor

logger = logging.getLogger(__name__)


class InteractionHandlers:
    """
    Handle drag and edge-click canvas events.

    This class is intentionally stateless: it translates user-interaction
    events into Editor calls.  The Editor owns the undo history, so every
    mutation is automatically recorded there.
    """

    def __init__(self, editor: "Editor"):
        self.editor = editor

    @handles_event(UserDragStartEvent)
    def process_drag_start(self, event: UserDragStartEvent):
        """Place an undo fence before a drag sequence begins."""
        self.editor.add_fence()

    @handles_event(UserDragUpdateEvent)
    def process_drag_update(self, event: UserDragUpdateEvent):
        """Forward absolute positions to editor (records MoveNodesToAction)."""
        logger.debug(f"Dragging {len(event.positions)} nodes to absolute positions")
        self.editor.move_nodes_to(event.positions)

    @handles_event(UserDragEndEvent)
    def process_drag_end(self, event: UserDragEndEvent):
        """Place a closing undo fence after a drag sequence ends."""
        self.editor.add_fence()

    @handles_event(EdgeClickedEvent)
    def process_edge_click(self, event: EdgeClickedEvent):
        """Log edge click; no editor mutation required."""
        logger.debug(f"Connection clicked: {event.edge_id}")
