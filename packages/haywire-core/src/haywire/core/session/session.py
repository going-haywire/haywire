# packages/haywire-core/src/haywire/core/session/session.py
"""
Session class representing a single browser connection in the Haywire UI system.
"""

from typing import Callable, TYPE_CHECKING, Type, TypeVar
import uuid
import logging

from haywire.core.session.context import SessionContext
from haywire.core.session.signals import Signal, SignalBus
from haywire.core.session.workspace.manager import WorkspaceManager

S = TypeVar("S", bound=Signal)

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

    One channel flows out of the session: a per-session typed signal bus.
    ``session.publish(s: Signal)`` fans out to subscribers registered via
    ``session.subscribe``. Editors auto-wire their ``@redraw_on`` /
    ``@react_on`` decorated methods at instantiation; the AppShell
    subscribes its workspace-mutation handlers (``Reveal``, ``Close``)
    directly.

    If ``type(s).cross_session is True`` the call delegates to
    ``SessionManager.broadcast`` which dispatches the signal to every
    session (including this one). Both observations (plain ``Signal``
    subclasses) and imperatives (``CommandSignal`` subclasses) travel
    through the same bus — the split is vocabulary, not transport.
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

        # Per-session typed signal bus — the only intra-session dispatch
        # channel. Editors auto-subscribe their ``@redraw_on`` /
        # ``@react_on`` decorated methods at instantiation; panels
        # contribute signal types via ``redraw_on=`` on ``@panel(...)``;
        # AppShell subscribes its workspace-mutation handlers directly.
        self._bus: SignalBus = SignalBus()

        logger.info(f"Session created: {self.session_id}")

    def publish(self, signal: Signal) -> None:
        """Publish a typed signal on the session's bus.

        Routing depends on ``type(signal).cross_session``:

        - ``False`` (local-only): fans out to every handler subscribed via
          :meth:`subscribe` for ``type(signal)``. Registration-order,
          error-isolated per handler.
        - ``True`` (cross-session): delegates to
          ``SessionManager.broadcast`` which dispatches to every session
          (including this one). The bus fan-out happens inside
          ``_dispatch`` on each receiving session.

        Args:
            signal: A :class:`Signal` instance — either an observation
                (plain ``Signal`` subclass) or an imperative
                (:class:`CommandSignal` subclass).
        """
        if type(signal).cross_session:
            self._session_manager.broadcast(signal)
            return

        self._bus.publish(signal)

    def subscribe(
        self,
        signal_type: Type[S],
        handler: Callable[[S], None],
    ) -> Callable[[], None]:
        """Subscribe ``handler`` to signals of exactly ``signal_type``.

        Thin pass-through to the session-local :class:`SignalBus`. Exact-
        class match (subclasses do not inherit subscriptions);
        registration-order dispatch; error-isolated per handler.

        Returns:
            An unsubscribe handle. The framework holds these handles to
            tear down editor / panel / shell subscriptions at cleanup /
            hot-reload.
        """
        return self._bus.subscribe(signal_type, handler)

    def _dispatch(self, signal: Signal) -> None:
        """Internal: deliver a signal originating elsewhere (e.g. a peer
        broadcast) without re-triggering broadcast.

        Called by ``SessionManager.broadcast`` on each receiving session.
        Bypasses the cross_session check on purpose — the broadcast is
        already happening.
        """
        self._bus.publish(signal)

    def cleanup(self) -> None:
        """Tear down per-session state.

        Drops every signal-bus subscription. AppShell teardown is driven
        upstream by studio.app.on_disconnect (Q7A: shell-upstream model) —
        Session is not involved in chrome cleanup.
        """
        self._bus.clear()
        logger.info(f"Session cleaned up: {self.session_id}")
