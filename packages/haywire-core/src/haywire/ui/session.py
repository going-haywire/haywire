# packages/haywire-core/src/haywire/ui/session.py
"""
Session class representing a single browser connection in the Haywire UI system.
"""

from typing import Dict, Callable, Optional, TYPE_CHECKING
import uuid
import logging

from .context import SessionContext
from .context_signals import ContextSignal, RevealRequest
from .workspace.manager import WorkspaceManager

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from haywire.ui.app.shell import AppShell
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.session_manager import SessionManager


class Session:
    """
    Represents a single browser session (one connected browser tab).

    Each session owns:
        - A SessionContext (selection, mode, active state)
        - A WorkspaceManager (layout, which editors where)
        - Editor instances (cached by the orchestrator)

    The Session is the bridge between the shared server-side data model
    and the per-client NiceGUI UI tree.

    Two channels flow through the AppShell:

    - ``session.signal(s: ContextSignal)`` — observation, fans out to
      local subscribers. If ``type(s).cross_session is True``, instead
      delegates to ``SessionManager.broadcast_signal`` which dispatches
      to every session (including this one) and stamps
      ``subject = Subject.peer(origin_id)`` on non-origin sessions.
    - ``session.reveal(r: RevealRequest)`` — command, point-to-point,
      local-only.
    """

    def __init__(
        self, project_state, workspace_manager: WorkspaceManager, session_manager: "SessionManager"
    ):
        """
        Create a new session.

        Args:
            project_state: The shared project state (graph data, settings, etc.).
            workspace_manager: Pre-configured WorkspaceManager for this session.
            session_manager: The SessionManager that owns this session, used for
                cross-session signal broadcasting.
        """
        self.session_id = str(uuid.uuid4())
        self.project_state = project_state
        self.workspace_manager: WorkspaceManager = workspace_manager
        self._session_manager: SessionManager = session_manager

        self.context = SessionContext(session_id=self.session_id, app=project_state)
        self.context.session = self

        # Active editor instances (keyed by area slot: 'left', 'middle', 'right', 'bottom')
        self._editors: Dict[str, "BaseEditor"] = {}

        # Two-callback wiring set by AppShell. Bound to
        # AppShell._on_signal / _on_reveal.
        self._signal_callback: Optional[Callable[[ContextSignal], None]] = None
        self._reveal_callback: Optional[Callable[[RevealRequest], None]] = None

        self._shell: Optional["AppShell"] = None

        logger.info(f"Session created: {self.session_id}")

    def set_shell(self, shell: "AppShell") -> None:
        """Register the AppShell that owns this session's slots."""
        self._shell = shell

    def set_signal_orchestrator(self, callback: Callable[[ContextSignal], None]) -> None:
        """Register the AppShell._on_signal handler.

        Args:
            callback: The orchestrator's signal handler (signature: signal -> None).
        """
        self._signal_callback = callback

    def set_reveal_orchestrator(self, callback: Callable[[RevealRequest], None]) -> None:
        """Register the AppShell._on_reveal handler.

        Args:
            callback: The orchestrator's reveal handler (signature: request -> None).
        """
        self._reveal_callback = callback

    def signal(self, signal: ContextSignal) -> None:
        """Emit a context signal.

        Routing depends on ``type(signal).cross_session``:

        - ``False`` (local-only): synchronously calls the registered signal
          callback with the signal.
        - ``True`` (cross-session): delegates to
          ``SessionManager.broadcast_signal``, which dispatches to *every*
          session (including this one) and stamps
          ``subject = Subject.peer(origin_id)`` on non-origin sessions.
          Origin receives subject=SELF (the unmodified signal).

        Either way the local callback is called exactly once.

        Args:
            signal: A ContextSignal instance describing what moved.
        """
        if type(signal).cross_session:
            self._session_manager.broadcast_signal(signal, origin_session_id=self.session_id)
            return

        if self._signal_callback is not None:
            try:
                self._signal_callback(signal)
            except Exception as e:
                logger.error(f"Session {self.session_id}: signal callback error: {e}")

    def reveal(self, request: RevealRequest) -> None:
        """Issue a reveal command (local-only).

        Args:
            request: A RevealRequest naming the editor to bring to the front.
        """
        if self._reveal_callback is not None:
            try:
                self._reveal_callback(request)
            except Exception as e:
                logger.error(f"Session {self.session_id}: reveal callback error: {e}")

    def _dispatch_signal(self, signal: ContextSignal) -> None:
        """Internal: deliver a signal originating elsewhere (e.g. a peer
        broadcast) without re-triggering broadcast.

        Called by ``SessionManager.broadcast_signal`` on each receiving
        session. Bypasses the cross_session check on purpose — the broadcast
        is already happening.
        """
        if self._signal_callback is not None:
            try:
                self._signal_callback(signal)
            except Exception as e:
                logger.error(f"Session {self.session_id}: dispatch_signal error: {e}")

    def cleanup(self) -> None:
        """Clean up all editor instances and managed slots.

        Called when the browser session disconnects.
        """
        if self._shell is not None:
            self._shell.cleanup()
            self._shell = None
        for editor in self._editors.values():
            editor.cleanup()
        self._editors.clear()
        self._signal_callback = None
        self._reveal_callback = None
        logger.info(f"Session cleaned up: {self.session_id}")
