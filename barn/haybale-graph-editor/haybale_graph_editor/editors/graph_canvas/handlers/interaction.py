"""
InteractionHandlers — drag and edge-click event handlers.

Stateless: all mutations are delegated to Editor, which records undo actions
internally.  Undo grouping is achieved by the fence pair on drag start/end.
"""

import logging
from typing import TYPE_CHECKING, Optional

from haywire.core.signals import GraphDataMutated
from haywire.ui.components.graph.event_definitions import (
    UserDragStartEvent,
    UserDragUpdateEvent,
    UserDragEndEvent,
    UserResizeEndEvent,
    EdgeClickedEvent,
)
from ..event_handlers import handles_event

if TYPE_CHECKING:
    from haywire.core.graph.editor import Editor
    from haywire.core.session.session import Session

logger = logging.getLogger(__name__)


class InteractionHandlers:
    """
    Handle drag and edge-click canvas events.

    This class is intentionally stateless: it translates user-interaction
    events into Editor calls.  The Editor owns the undo history, so every
    mutation is automatically recorded there.

    ``session`` is used only to publish ``GraphDataMutated`` after a mutation
    that does NOT go through the validation pipeline (a resize writes cosmetic
    size props that never mark a node dirty, so nothing else broadcasts). That
    broadcast is what refreshes the toolbar's undo/redo enablement — without it
    the undo button stays stale until the next validating op.
    """

    def __init__(self, editor: "Editor", session: "Optional[Session]" = None):
        self.editor = editor
        self._session = session

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

    @handles_event(UserResizeEndEvent)
    def process_resize_end(self, event: UserResizeEndEvent):
        """Commit a resize gesture as ONE undo fence: size write (+ optional move).

        Mirrors the drag fence pattern (start/end add_fence). The size goes
        through set_property (undoable SetPropertyAction); a top/left drag that
        moved the origin adds move_nodes_to (MoveNodesToAction) inside the same
        fence, so one Ctrl-Z reverts both size and position.
        """
        # prefer_setting: size props live on the settings bag; without it a
        # node exposing a port named "width"/"height" (e.g. a frame-info node's
        # outlets) would swallow the write and the resize would not stick.
        self.editor.add_fence()
        self.editor.set_property(event.nodeId, "size_adapt", event.size_adapt, prefer_setting=True)
        self.editor.set_property(event.nodeId, "width", event.width, prefer_setting=True)
        self.editor.set_property(event.nodeId, "height", event.height, prefer_setting=True)
        if event.posX is not None and event.posY is not None:
            self.editor.move_nodes_to({event.nodeId: {"x": event.posX, "y": event.posY}})
        self.editor.add_fence()

        # Size props are cosmetic — they never mark a node dirty, so the
        # validation pipeline (which is what normally broadcasts
        # GraphDataMutated) does not run. Publish it explicitly so the toolbar's
        # undo/redo enablement refreshes now, not on the next validating op.
        if self._session is not None:
            self._session.publish(GraphDataMutated())

    @handles_event(EdgeClickedEvent)
    def process_edge_click(self, event: EdgeClickedEvent):
        """Log edge click; no editor mutation required."""
        logger.debug(f"Connection clicked: {event.edge_id}")
