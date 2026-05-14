# packages/haywire-core/src/haywire/core/session/session.py
"""
Session class representing a single browser connection in the Haywire UI system.
"""

from typing import Callable, Optional, TYPE_CHECKING, Type
import uuid
import logging

from haywire.core.session.bus import EventBus
from haywire.core.session.context import SessionContext
from haywire.core.session.signals_and_lifecycle import ContextSignal, LifecycleCommand
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

    Two channels flow out of the session:

    - **Event bus** (observation). ``session.publish(s: ContextSignal)``
      fans out to subscribers registered via ``session.subscribe``;
      editors auto-wire their ``@redraw_on`` / ``@react_on`` decorated
      methods at instantiation. ``session.signal(...)`` is a thin alias
      for ``publish``, kept for legacy emit-site call shapes. If
      ``type(s).cross_session is True`` the call delegates to
      ``SessionManager.broadcast_signal`` which dispatches to every
      session (including this one) and stamps
      ``subject = Subject.peer(origin_id)`` on non-origin sessions.
    - **Lifecycle channel** (imperative). ``session.lifecycle(cmd)``
      mutates the workspace tree (``Reveal`` brings an editor to the
      front, ``Close`` removes tabs bound to a binding_id). The AppShell
      registers itself via ``set_lifecycle_orchestrator``. Local by
      default; if ``type(cmd).cross_session is True`` (e.g.
      ``BroadcastClose``) delegates to
      ``SessionManager.broadcast_lifecycle`` so every session's AppShell
      receives the command.
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
        # channel for ContextSignals. Editors auto-subscribe their
        # ``@redraw_on`` / ``@react_on`` decorated methods at instantiation;
        # panels contribute event types via ``redraw_on=`` on
        # ``@panel(...)``.
        self._bus: EventBus = EventBus()

        # Lifecycle-command callback. Bound to ``AppShell._on_lifecycle``
        # by the AppShell at startup. AppShell teardown is driven upstream
        # by studio.app.on_disconnect (Q7A: shell-upstream model) — Session
        # is not involved.
        self._lifecycle_callback: Optional[Callable[[LifecycleCommand], None]] = None

        logger.info(f"Session created: {self.session_id}")

    def set_lifecycle_orchestrator(self, callback: Callable[[LifecycleCommand], None]) -> None:
        """Register the AppShell._on_lifecycle handler.

        Args:
            callback: The orchestrator's lifecycle-command handler
                (signature: command -> None).
        """
        self._lifecycle_callback = callback

    def publish(self, event: ContextSignal) -> None:
        """Publish a typed event on the session's bus.

        Routing depends on ``type(event).cross_session``:

        - ``False`` (local-only): fans out to every handler subscribed via
          :meth:`subscribe` for ``type(event)``. Registration-order,
          error-isolated per handler.
        - ``True`` (cross-session): delegates to
          ``SessionManager.broadcast_signal`` which dispatches to every
          session (including this one) and stamps
          ``subject = Subject.peer(origin_id)`` on non-origin sessions.
          The bus fan-out happens inside ``_dispatch_signal`` on each
          receiving session, so cross-session subscribers see peer-
          stamped events.

        Args:
            event: A ContextSignal instance describing what happened.
        """
        if type(event).cross_session:
            self._session_manager.broadcast_signal(event, origin_session_id=self.session_id)
            return

        self._bus.publish(event)

    # ``signal`` is the legacy emit name kept as a thin alias so existing
    # call sites stay valid without churn. New code should call
    # :meth:`publish` directly.
    signal = publish

    def subscribe(
        self,
        event_type: Type[ContextSignal],
        handler: Callable[[ContextSignal], None],
    ) -> Callable[[], None]:
        """Subscribe ``handler`` to events of exactly ``event_type``.

        Thin pass-through to the session-local :class:`EventBus`. Exact-
        class match (subclasses do not inherit subscriptions);
        registration-order dispatch; error-isolated per handler.

        Returns:
            An unsubscribe handle. The framework holds these handles to
            tear down editor / panel subscriptions at cleanup / hot-reload.
        """
        return self._bus.subscribe(event_type, handler)

    def lifecycle(self, command: LifecycleCommand) -> None:
        """Issue a lifecycle command.

        Routing depends on ``type(command).cross_session``:

        - ``False`` (default, local-only): synchronously calls the
          registered lifecycle callback (the AppShell) which dispatches
          per-command — ``Reveal`` is point-to-point (one slot resolved
          from ``editor.class_identity.default_slot``); ``Close`` is
          fan-out across slots.
        - ``True`` (cross-session, e.g. ``BroadcastClose``): delegates
          to ``SessionManager.broadcast_lifecycle`` which dispatches the
          command to every session (including this one). Each session's
          AppShell handles the command locally.

        Args:
            command: A LifecycleCommand subclass.
        """
        if type(command).cross_session:
            self._session_manager.broadcast_lifecycle(command, origin_session_id=self.session_id)
            return

        if self._lifecycle_callback is not None:
            try:
                self._lifecycle_callback(command)
            except Exception as e:
                logger.error(f"Session {self.session_id}: lifecycle callback error: {e}")

    def _dispatch_signal(self, signal: ContextSignal) -> None:
        """Internal: deliver a signal originating elsewhere (e.g. a peer
        broadcast) without re-triggering broadcast.

        Called by ``SessionManager.broadcast_signal`` on each receiving
        session. Bypasses the cross_session check on purpose — the
        broadcast is already happening. Peer-stamped signals reach every
        local subscriber of ``type(signal)``.
        """
        self._bus.publish(signal)

    def _dispatch_lifecycle(self, command: LifecycleCommand) -> None:
        """Internal: deliver a lifecycle command originating elsewhere
        (e.g. a peer broadcast) without re-triggering broadcast.

        Called by ``SessionManager.broadcast_lifecycle`` on each receiving
        session. Bypasses the cross_session check on purpose — the broadcast
        is already happening.
        """
        if self._lifecycle_callback is not None:
            try:
                self._lifecycle_callback(command)
            except Exception as e:
                logger.error(f"Session {self.session_id}: dispatch_lifecycle error: {e}")

    def cleanup(self) -> None:
        """Tear down per-session state.

        Clears the lifecycle callback slot and drops every event-bus
        subscription. AppShell teardown is driven upstream by
        studio.app.on_disconnect (Q7A: shell-upstream model) — Session is
        not involved in chrome cleanup.
        """
        self._lifecycle_callback = None
        self._bus.clear()
        logger.info(f"Session cleaned up: {self.session_id}")
