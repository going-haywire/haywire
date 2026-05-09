# packages/haywire-core/src/haywire/core/session/session.py
"""
Session class representing a single browser connection in the Haywire UI system.
"""

from typing import Callable, Optional, TYPE_CHECKING
import uuid
import logging

from haywire.core.session.context import SessionContext
from haywire.core.session.context_signals import ContextSignal, LifecycleCommand
from haywire.core.session.workspace.manager import WorkspaceManager

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from haywire.core.session.session_manager import SessionManager


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
    - ``session.lifecycle(cmd: LifecycleCommand)`` — imperative
      mutation of the workspace tree (``Reveal`` brings an editor to
      the front, ``Close`` removes tabs bound to a payload). Local-only.
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
        self._session_manager: "SessionManager" = session_manager

        self.context = SessionContext(session_id=self.session_id, app=project_state)
        self.context.session = self

        # Two-callback wiring. Signal and lifecycle are bound to
        # AppShell._on_signal / _on_lifecycle by the AppShell at startup.
        # AppShell teardown is driven upstream by studio.app.on_disconnect
        # (Q7A: shell-upstream model) — Session is not involved.
        self._signal_callback: Optional[Callable[[ContextSignal], None]] = None
        self._lifecycle_callback: Optional[Callable[[LifecycleCommand], None]] = None

        logger.info(f"Session created: {self.session_id}")

    def set_signal_orchestrator(self, callback: Callable[[ContextSignal], None]) -> None:
        """Register the AppShell._on_signal handler.

        Args:
            callback: The orchestrator's signal handler (signature: signal -> None).
        """
        self._signal_callback = callback

    def set_lifecycle_orchestrator(self, callback: Callable[[LifecycleCommand], None]) -> None:
        """Register the AppShell._on_lifecycle handler.

        Args:
            callback: The orchestrator's lifecycle-command handler
                (signature: command -> None).
        """
        self._lifecycle_callback = callback

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

    def lifecycle(self, command: LifecycleCommand) -> None:
        """Issue a lifecycle command (local-only).

        Routes through the AppShell, which dispatches per-command:
        ``Reveal`` is point-to-point (one slot resolved from
        ``editor.class_identity.default_slot``); ``Close`` is fan-out
        across slots.

        Args:
            command: A LifecycleCommand subclass (Reveal / Close).
        """
        if self._lifecycle_callback is not None:
            try:
                self._lifecycle_callback(command)
            except Exception as e:
                logger.error(f"Session {self.session_id}: lifecycle callback error: {e}")

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
        """Tear down per-session state.

        Clears the signal/lifecycle callback slots. AppShell teardown is
        driven upstream by studio.app.on_disconnect (Q7A: shell-upstream
        model) — Session is not involved in chrome cleanup.
        """
        self._signal_callback = None
        self._lifecycle_callback = None
        logger.info(f"Session cleaned up: {self.session_id}")
