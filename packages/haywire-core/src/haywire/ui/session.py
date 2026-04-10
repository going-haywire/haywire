# packages/haywire-core/src/haywire/ui/session.py
"""
Session class representing a single browser connection in the Haywire UI system.
"""

from typing import Dict, Callable, Optional, TYPE_CHECKING
import uuid
import logging

from .context import SessionContext
from .context_events import ContextChangedEvent
from .workspace.manager import WorkspaceManager

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor


class Session:
    """
    Represents a single browser session (one connected browser tab).

    Each session owns:
        - A SessionContext (selection, mode, active state)
        - A WorkspaceManager (layout, which editors where)
        - Editor instances (cached by the orchestrator)

    The Session is the bridge between the shared server-side data model
    and the per-client NiceGUI UI tree.

    Context change flow:
        1. Any component calls session.notify_context_changed(event).
        2. Session forwards the event to the orchestrator callback (AppShell).
        3. The orchestrator runs the poll/draw cycle on active editors.
    """

    def __init__(self, project_state, workspace_manager: WorkspaceManager):
        """
        Create a new session.

        Args:
            project_state: The shared project state (graph data, settings, etc.).
            workspace_manager: Pre-configured WorkspaceManager for this session.
        """
        self.session_id = str(uuid.uuid4())
        self.project_state = project_state
        self.context = SessionContext(session_id=self.session_id, app=project_state)
        self.context.session = self
        self.workspace_manager = workspace_manager

        # Active editor instances (keyed by area slot: 'left', 'middle', 'right', 'bottom')
        self._editors: Dict[str, "BaseEditor"] = {}

        # Single orchestrator callback set by AppShell
        self._orchestrator_callback: Optional[Callable[[ContextChangedEvent, SessionContext], None]] = None

        logger.info(f"Session created: {self.session_id}")

    def set_orchestrator(self, callback: Callable[["ContextChangedEvent", "SessionContext"], None]) -> None:
        """Set the single orchestrator callback for context change notifications.

        Args:
            callback: The orchestrator's context-change handler
                      (signature: event, context -> None).
        """
        self._orchestrator_callback = callback

    def notify_context_changed(self, event: ContextChangedEvent) -> None:
        """
        Forward a context change to the orchestrator.

        Called when selection changes, graph switches, mode changes, etc.
        The orchestrator (AppShell) runs the poll/draw cycle.

        Args:
            event: The ContextChangedEvent describing what changed.
        """
        if self._orchestrator_callback is not None:
            try:
                self._orchestrator_callback(event, self.context)
            except Exception as e:
                logger.error(f"Session {self.session_id}: orchestrator callback error: {e}")

    def cleanup(self) -> None:
        """Clean up all editor instances.

        Called when the browser session disconnects.
        """
        for editor in self._editors.values():
            editor.cleanup()
        self._editors.clear()
        self._orchestrator_callback = None
        logger.info(f"Session cleaned up: {self.session_id}")
