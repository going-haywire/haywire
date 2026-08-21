# packages/haywire-core/src/haywire/core/session/session_manager.py

import logging
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.session.session import Session
    from haywire.core.signals import SignalDispatcher
    from haywire.core.state import LibraryStateContainer


logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages all active browser Sessions::

        manager = SessionManager(dispatcher=dispatcher, container=app.library_state_container)
        session = manager.create_session(app_state=app, workspace_manager=ws)
        manager.remove_session(session.session_id)

    Lifecycle only. Signal fan-out is
    :class:`~haywire.core.signals.dispatcher.SignalDispatcher`'s job — this
    class used to own a ``broadcast`` method, but of the five call paths that
    reached it only ``Session.publish`` had anything to do with sessions. The
    rest (``AppState._signal_emit``, ``FarmhandContext.broadcast``, the studio
    error/activity/presence bridges) wanted a channel and were handed a
    registry. They now call ``SignalDispatcher.broadcast`` directly.

    Sessions are not registered with the dispatcher here: ``SignalPeer``
    registers itself on construction and unregisters in ``cleanup()``, which
    :meth:`remove_session` already calls. That keeps eviction (ADR 0027)
    correct for free — see ``auth/eviction.py``, which needs no knowledge of
    peers at all.
    """

    def __init__(self, dispatcher: "SignalDispatcher", container: "LibraryStateContainer"):
        self._sessions: Dict[str, "Session"] = {}
        self._dispatcher = dispatcher
        self._container = container

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def create_session(self, **session_kwargs) -> "Session":
        """
        Create a new Session and register it.

        All keyword arguments are forwarded to the Session constructor.
        ``dispatcher=self._dispatcher`` is injected automatically so callers do
        not pass it — and so every session lands in the same fan-out.

        After Session construction, the LibraryStateContainer is told to
        attach this session_id — every registered SessionState class gets
        a fresh instance for this session, with on_enable called.

        Returns:
            The newly created Session.
        """
        from haywire.core.session.session import Session

        session = Session(dispatcher=self._dispatcher, **session_kwargs)
        self._sessions[session.session_id] = session
        # Attach AFTER Session is fully constructed so SessionContext exists
        # and SessionDataNamespace can immediately resolve lookups.
        self._container.attach_session_with_ref(session.session_id, session)
        logger.info(f"SessionManager: created session {session.session_id[:8]}")
        return session

    def remove_session(self, session_id: str) -> None:
        """
        Clean up and remove a session by ID.

        ``Session.cleanup()`` unregisters the session from the dispatcher, so
        a removed session stops receiving broadcasts immediately — including
        when the caller is ``evict_principal``.

        Args:
            session_id: The full session ID string.
        """
        session = self._sessions.pop(session_id, None)
        if session is not None:
            try:
                session.cleanup()
            except Exception as e:
                logger.warning(f"SessionManager: error cleaning up session {session_id[:8]}: {e}")
        # Detach AFTER cleanup so a panel/editor reading ctx.data[X] during its
        # own cleanup still sees the instance, and on_disable can't observe a
        # half-torn-down session. The call is idempotent — safe to run even when
        # the session was unknown (e.g., already removed).
        self._container.detach_session(session_id)
        if session is not None:
            logger.info(f"SessionManager: removed session {session_id[:8]}")

    def get_session(self, session_id: str) -> Optional["Session"]:
        """Return the session for the given ID, or None if not found."""
        return self._sessions.get(session_id)

    @property
    def active_sessions(self) -> Dict[str, "Session"]:
        """Read-only view of all active browser sessions keyed by session_id.

        Only ever contains :class:`Session` instances — non-browser peers
        (the Farmhand host, a CLI) live in the dispatcher's registry, never
        here. Presence and eviction rely on that: both read ``.context``,
        which a bare peer does not have.
        """
        return dict(self._sessions)

    @property
    def session_count(self) -> int:
        """Number of currently active sessions."""
        return len(self._sessions)

    def cleanup_all(self) -> None:
        """Clean up all sessions (call on application shutdown)."""
        for session_id in list(self._sessions.keys()):
            self.remove_session(session_id)
        logger.info("SessionManager: all sessions cleaned up")
