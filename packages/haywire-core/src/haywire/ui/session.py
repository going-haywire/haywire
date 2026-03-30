# packages/haywire-core/src/haywire/ui/session.py
"""
Session class representing a single browser connection in the Haywire UI system.
"""

from typing import Dict, List, Callable, TYPE_CHECKING
import uuid
import logging

logger = logging.getLogger(__name__)

from haywire.ui.context import SessionContext
from haywire.ui.context_events import ContextChangedEvent
from haywire.ui.workspace.manager import WorkspaceManager

if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor


class Session:
    """
    Represents a single browser session (one connected browser tab).

    Each session owns:
        - A SessionContext (selection, mode, active state)
        - A WorkspaceManager (layout, which editors where)
        - Editor instances (one per area slot)
        - Context change subscriptions

    The Session is the bridge between the shared server-side data model
    and the per-client NiceGUI UI tree.

    Lifecycle:
        1. Created on client connect (NiceGUI app.on_connect)
        2. AppShell builds the workspace layout using active workspace state
        3. Editors are instantiated into areas based on active workspace
        4. Editors subscribe to context changes via subscribe_context_changes()
        5. Session destroyed on client disconnect (cleanup())
    """

    def __init__(self, project_state, project_path=None):
        """
        Create a new session.

        Args:
            project_state: The shared project state (graph data, settings, etc.).
            project_path: Optional path to the project folder for workspace persistence.
        """
        self.session_id = str(uuid.uuid4())
        self.project_state = project_state
        self.context = SessionContext(session_id=self.session_id, app=project_state)
        self.context.session = self
        self.workspace_manager = WorkspaceManager(project_path=project_path)

        # Active editor instances (keyed by area slot: 'left', 'middle', 'right', 'bottom')
        self._editors: Dict[str, "BaseEditor"] = {}

        # Context change subscribers (editor.on_context_changed callbacks)
        self._context_subscribers: List[Callable] = []

        logger.info(f"Session created: {self.session_id}")

    def notify_context_changed(self, event: ContextChangedEvent) -> None:
        """
        Broadcast a context change to all editors in this session.

        Called when selection changes, graph switches, mode changes, etc.
        Each subscribed editor will re-evaluate its panels.

        Args:
            event: The ContextChangedEvent describing what changed.
        """
        for subscriber in self._context_subscribers:
            try:
                subscriber(event, self.context)
            except Exception as e:
                logger.error(f"Session {self.session_id}: context subscriber error: {e}")

    def subscribe_context_changes(self, callback: Callable) -> None:
        """Register a callback to receive context change notifications.

        Args:
            callback: Callable with signature (event: ContextChangedEvent, context: SessionContext).
        """
        if callback not in self._context_subscribers:
            self._context_subscribers.append(callback)

    def unsubscribe_context_changes(self, callback: Callable) -> None:
        """Unregister a previously registered context change callback.

        Args:
            callback: The callback to remove.
        """
        if callback in self._context_subscribers:
            self._context_subscribers.remove(callback)

    def cleanup(self) -> None:
        """Clean up all editor instances and subscriptions.

        Called when the browser session disconnects.
        """
        for editor in self._editors.values():
            editor.cleanup()
        self._editors.clear()
        self._context_subscribers.clear()
        logger.info(f"Session cleaned up: {self.session_id}")
