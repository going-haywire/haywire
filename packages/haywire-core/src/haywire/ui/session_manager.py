# packages/haywire-core/src/haywire/ui/session_manager.py
"""
SessionManager — manages the lifecycle of all active browser sessions.

Each browser connection gets its own Session. The SessionManager creates,
tracks, and removes sessions. It also provides broadcast() to fan a
ContextChangedEvent to every session — used for cross-session updates.
"""

import logging
from typing import Dict, Optional, TYPE_CHECKING

from haywire.ui.context_events import ContextChangedEvent

if TYPE_CHECKING:
    from haywire.ui.session import Session


logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages all active Sessions across browser connections.

    Usage:
        manager = SessionManager()
        session = manager.create_session(project_state=app, workspace_manager=ws)
        manager.remove_session(session.session_id)
        manager.broadcast(event)
    """

    def __init__(self):
        self._sessions: Dict[str, "Session"] = {}

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, **session_kwargs) -> "Session":
        """
        Create a new Session and register it.

        All keyword arguments are forwarded to the Session constructor.
        ``session_manager=self`` is injected automatically so callers do
        not pass it.

        Returns:
            The newly created Session.
        """
        from haywire.ui.session import Session

        session = Session(session_manager=self, **session_kwargs)
        self._sessions[session.session_id] = session
        logger.info(f"SessionManager: created session {session.session_id[:8]}")
        return session

    def remove_session(self, session_id: str) -> None:
        """
        Clean up and remove a session by ID.

        Args:
            session_id: The full session ID string.
        """
        session = self._sessions.pop(session_id, None)
        if session is not None:
            try:
                session.cleanup()
            except Exception as e:
                logger.warning(f"SessionManager: error cleaning up session {session_id[:8]}: {e}")
            logger.info(f"SessionManager: removed session {session_id[:8]}")

    def get_session(self, session_id: str) -> Optional["Session"]:
        """Return the session for the given ID, or None if not found."""
        return self._sessions.get(session_id)

    @property
    def active_sessions(self) -> Dict[str, "Session"]:
        """Read-only view of all active sessions keyed by session_id."""
        return dict(self._sessions)

    @property
    def session_count(self) -> int:
        """Number of currently active sessions."""
        return len(self._sessions)

    # ------------------------------------------------------------------
    # Broadcast helpers
    # ------------------------------------------------------------------

    def broadcast(self, event: ContextChangedEvent) -> None:
        """Fan an event out to every registered session.

        Used for cross-session notifications (e.g. DATA_MUTATED after a
        graph edit). Consumers already re-read their own ground-truth state
        when notified, so unconditional fan-out is safe — a session that
        doesn't care no-ops on receipt.
        """
        failed = []
        for session_id, session in list(self._sessions.items()):
            try:
                session.notify_context_changed(event)
            except Exception as e:
                logger.warning(f"SessionManager: broadcast failed for session {session_id[:8]}: {e}")
                failed.append(session_id)
        if failed:
            logger.warning(f"SessionManager: {len(failed)} session(s) failed during broadcast")

    def cleanup_all(self) -> None:
        """Clean up all sessions (call on application shutdown)."""
        for session_id in list(self._sessions.keys()):
            self.remove_session(session_id)
        logger.info("SessionManager: all sessions cleaned up")
