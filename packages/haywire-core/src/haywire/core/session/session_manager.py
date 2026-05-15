# packages/haywire-core/src/haywire/ui/session_manager.py
"""
SessionManager — manages the lifecycle of all active browser sessions.

Each browser connection gets its own Session. The SessionManager creates,
tracks, and removes sessions. It also provides :meth:`broadcast` to fan a
:class:`~haywire.core.session.signals.Signal` out to every session — used for
cross-session updates when the signal class declares ``cross_session = True``.
"""

import logging
from typing import Dict, Optional, TYPE_CHECKING

from haywire.core.session.signals import Signal

if TYPE_CHECKING:
    from haywire.core.session.session import Session
    from haywire.core.state import LibraryStateContainer


logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages all active Sessions across browser connections.

    Usage:
        manager = SessionManager(container=app.library_state_container)
        session = manager.create_session(project_state=app, workspace_manager=ws)
        manager.remove_session(session.session_id)
        manager.broadcast(signal)
    """

    def __init__(self, container: "LibraryStateContainer"):
        self._sessions: Dict[str, "Session"] = {}
        self._container = container
        self._container.bind_session_manager(self)

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, **session_kwargs) -> "Session":
        """
        Create a new Session and register it.

        All keyword arguments are forwarded to the Session constructor.
        ``session_manager=self`` is injected automatically so callers do
        not pass it.

        After Session construction, the LibraryStateContainer is told to
        attach this session_id — every registered SessionState class gets
        a fresh instance for this session, with on_enable called.

        Returns:
            The newly created Session.
        """
        from haywire.core.session.session import Session

        session = Session(session_manager=self, **session_kwargs)
        self._sessions[session.session_id] = session
        # Attach AFTER Session is fully constructed so SessionContext exists
        # and SessionDataNamespace can immediately resolve lookups.
        self._container.attach_session_with_ref(session.session_id, session)
        logger.info(f"SessionManager: created session {session.session_id[:8]}")
        return session

    def remove_session(self, session_id: str) -> None:
        """
        Clean up and remove a session by ID.

        Order: session.cleanup() runs first (UI / editors / slots tear
        down), then container.detach_session() runs (SessionState
        on_disable fires, instances dropped). This way a panel/editor
        that reads ctx.data[X] during its own cleanup still sees the
        instance.

        Args:
            session_id: The full session ID string.
        """
        session = self._sessions.pop(session_id, None)
        if session is not None:
            try:
                session.cleanup()
            except Exception as e:
                logger.warning(f"SessionManager: error cleaning up session {session_id[:8]}: {e}")
        # Detach AFTER cleanup so on_disable can't observe a half-torn-down
        # session. The call is idempotent — safe to run even when the session
        # was unknown (e.g., already removed).
        self._container.detach_session(session_id)
        if session is not None:
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

    def broadcast(self, signal: Signal) -> None:
        """Fan a :class:`Signal` out to every registered session.

        Callers normally reach this path via ``Session.publish(signal)``
        when ``type(signal).cross_session is True``. Used both for
        observations (e.g. ``GraphDataMutated`` so peer sessions refresh
        their views) and imperatives (e.g. ``BroadcastClose`` so peer
        sessions close tabs bound to a vanishing entity).

        Per-peer exceptions are swallowed and logged — a subscriber
        raising in one session does not abort delivery to others. See
        §6.5 of the design doc for the cross-session delivery contract.

        Args:
            signal: The :class:`Signal` to fan out.
        """
        failed = []
        for session_id, session in list(self._sessions.items()):
            try:
                session._dispatch(signal)
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
