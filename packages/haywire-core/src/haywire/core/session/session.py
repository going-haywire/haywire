# packages/haywire-core/src/haywire/core/session/session.py
"""
Session class representing a single browser connection in the Haywire UI system.
"""

from typing import Callable, TYPE_CHECKING, Type, TypeVar
import uuid
import logging

from haywire.core.session.bus import EventBus
from haywire.core.session.context import SessionContext
from haywire.core.session.events import Event
from haywire.core.session.workspace.manager import WorkspaceManager

E = TypeVar("E", bound=Event)

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

    One channel flows out of the session: a per-session typed event bus.
    ``session.publish(e: Event)`` fans out to subscribers registered via
    ``session.subscribe``. Editors auto-wire their ``@redraw_on`` /
    ``@react_on`` decorated methods at instantiation; the AppShell
    subscribes its workspace-mutation handlers (``Reveal``, ``Close``)
    directly. ``session.signal(...)`` is a thin alias for ``publish``,
    kept for legacy emit-site call shapes.

    If ``type(e).cross_session is True`` the call delegates to
    ``SessionManager.broadcast`` which dispatches the event to every
    session (including this one). Both observations (``ContextSignal``)
    and imperatives (``LifecycleCommand``) travel through the same bus —
    the split is vocabulary, not transport.
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

        # Per-session typed event bus — the only intra-session dispatch
        # channel. Editors auto-subscribe their ``@redraw_on`` /
        # ``@react_on`` decorated methods at instantiation; panels
        # contribute event types via ``redraw_on=`` on ``@panel(...)``;
        # AppShell subscribes its workspace-mutation handlers directly.
        self._bus: EventBus = EventBus()

        logger.info(f"Session created: {self.session_id}")

    def publish(self, event: Event) -> None:
        """Publish a typed event on the session's bus.

        Routing depends on ``type(event).cross_session``:

        - ``False`` (local-only): fans out to every handler subscribed via
          :meth:`subscribe` for ``type(event)``. Registration-order,
          error-isolated per handler.
        - ``True`` (cross-session): delegates to
          ``SessionManager.broadcast`` which dispatches to every session
          (including this one). The bus fan-out happens inside
          ``_dispatch`` on each receiving session.

        Args:
            event: An :class:`Event` instance — either a
                :class:`ContextSignal` (observation) or a
                :class:`LifecycleCommand` (imperative).
        """
        if type(event).cross_session:
            self._session_manager.broadcast(event, origin_session_id=self.session_id)
            return

        self._bus.publish(event)

    # ``signal`` is the legacy emit name kept as a thin alias so existing
    # call sites stay valid without churn. New code should call
    # :meth:`publish` directly.
    signal = publish

    def subscribe(
        self,
        event_type: Type[E],
        handler: Callable[[E], None],
    ) -> Callable[[], None]:
        """Subscribe ``handler`` to events of exactly ``event_type``.

        Thin pass-through to the session-local :class:`EventBus`. Exact-
        class match (subclasses do not inherit subscriptions);
        registration-order dispatch; error-isolated per handler.

        Returns:
            An unsubscribe handle. The framework holds these handles to
            tear down editor / panel / shell subscriptions at cleanup /
            hot-reload.
        """
        return self._bus.subscribe(event_type, handler)

    def _dispatch(self, event: Event) -> None:
        """Internal: deliver an event originating elsewhere (e.g. a peer
        broadcast) without re-triggering broadcast.

        Called by ``SessionManager.broadcast`` on each receiving session.
        Bypasses the cross_session check on purpose — the broadcast is
        already happening.
        """
        self._bus.publish(event)

    def cleanup(self) -> None:
        """Tear down per-session state.

        Drops every event-bus subscription. AppShell teardown is driven
        upstream by studio.app.on_disconnect (Q7A: shell-upstream model) —
        Session is not involved in chrome cleanup.
        """
        self._bus.clear()
        logger.info(f"Session cleaned up: {self.session_id}")
