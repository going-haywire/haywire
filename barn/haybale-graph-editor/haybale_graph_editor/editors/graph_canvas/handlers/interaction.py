"""
InteractionHandlers — drag and edge-click event handlers.

Stateless: all mutations are delegated to the level's Editor, reached through the
edit route, which records undo actions internally. Undo grouping is achieved by
the fence pair on drag start/end.
"""

import logging
from typing import TYPE_CHECKING, Optional

from haywire.core.access import LevelMode
from haywire.core.node.layout import PATCH, LayoutChannel
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
    from haywire.core.graph.edit_route import EditRoute
    from haywire.core.session.session import Session

logger = logging.getLogger(__name__)


class InteractionHandlers:
    """
    Handle drag and edge-click canvas events.

    This class is intentionally stateless: it translates user-interaction
    events into Editor calls.  The Editor owns the undo history, so every
    mutation is automatically recorded there. Each handler does nothing while
    the route hands out no Editor (below level mode edit).

    ``session`` is used only to publish ``GraphDataMutated`` after a resize,
    which is announced as a value edit and so raises no ``GraphDataMutated`` of
    its own. That broadcast is what refreshes the header's undo/redo
    enablement.
    """

    def __init__(
        self,
        route: "EditRoute",
        session: "Optional[Session]" = None,
        channel: LayoutChannel = PATCH,
    ):
        """Set up the handlers for ``route``'s graph.

        Args:
            channel: The props fields this canvas lays its nodes out with.
        """
        self.route = route
        self._session = session
        self.channel = channel

    def _to_channel(self, positions: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
        """Return ``positions`` from canvas coordinates in this canvas's channel coordinates."""
        out: dict[str, dict[str, float]] = {}
        for node_id, pos in positions.items():
            x, y = self.channel.from_canvas(pos["x"], pos["y"])
            out[node_id] = {"x": x, "y": y}
        return out

    @handles_event(UserDragStartEvent)
    def process_drag_start(self, event: UserDragStartEvent):
        """Place an undo fence before a drag sequence begins."""
        editor = self.route.editor()
        if editor is None:
            return
        editor.add_fence()

    @handles_event(UserDragUpdateEvent)
    def process_drag_update(self, event: UserDragUpdateEvent):
        """Forward absolute positions to editor (records MoveNodesToAction)."""
        editor = self.route.editor()
        if editor is None:
            return
        logger.debug(f"Dragging {len(event.positions)} nodes to absolute positions")
        editor.move_nodes_to(self._to_channel(event.positions), self.channel)

    @handles_event(UserDragEndEvent)
    def process_drag_end(self, event: UserDragEndEvent):
        """Place a closing undo fence after a drag sequence ends."""
        editor = self.route.editor()
        if editor is None:
            return
        editor.add_fence()

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
        editor = self.route.editor()
        if editor is None:
            return
        editor.add_fence()
        channel = self.channel
        editor.set_property(event.nodeId, channel.size_adapt, event.size_adapt, prefer_setting=True)
        editor.set_property(event.nodeId, channel.width, event.width, prefer_setting=True)
        editor.set_property(event.nodeId, channel.height, event.height, prefer_setting=True)
        if event.posX is not None and event.posY is not None:
            editor.move_nodes_to(
                self._to_channel({event.nodeId: {"x": event.posX, "y": event.posY}}), channel
            )
        editor.add_fence()

        # The size writes mark a value edit, which announces at most the unsaved
        # flip; publish GraphDataMutated so undo/redo enablement refreshes now.
        if self._session is not None:
            self._session.publish(GraphDataMutated())

    @handles_event(EdgeClickedEvent, access=LevelMode.VIEW)
    def process_edge_click(self, event: EdgeClickedEvent):
        """Log edge click; no editor mutation required."""
        logger.debug(f"Connection clicked: {event.edge_id}")
