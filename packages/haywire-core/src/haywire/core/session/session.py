# packages/haywire-core/src/haywire/core/session/session.py
"""
Session class representing a single browser connection in the Haywire UI system.
"""

import logging
from typing import TYPE_CHECKING

from haywire.core.session.context import SessionContext
from haywire.core.session.protocols import IAppState
from haywire.core.session.workspace.manager import WorkspaceManager
from haywire.core.signals import SignalPeer

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from haywire.core.signals import SignalDispatcher


class Session(SignalPeer):
    """
    Represents a single browser session (one connected browser tab).

    Each session owns:
        - A SessionContext (selection, mode, active state)
        - A WorkspaceManager (layout, which editors where)
        - Editor instances (cached by the orchestrator)

    The Session is the bridge between the shared server-side data model
    and the per-client NiceGUI UI tree.

    Signal mechanics come from :class:`~haywire.core.signals.peer.SignalPeer`:
    ``publish`` / ``subscribe`` / ``_dispatch`` / ``cleanup``, plus dispatcher
    membership. A Session is the browser-tab kind of peer, adding a
    ``SessionContext``, a ``WorkspaceManager``, and the shared app state.

    Editors auto-wire their ``@redraw_on`` / ``@react_on`` methods at
    instantiation; panels contribute types via ``redraw_on=`` on ``@panel(...)``;
    the AppShell subscribes ``Reveal`` / ``Close`` directly.
    """

    def __init__(
        self,
        app_state: "IAppState",
        workspace_manager: WorkspaceManager,
        dispatcher: "SignalDispatcher",
    ):
        """
        Create a new session.

        Args:
            app_state: The shared project state (graph data, settings, etc.).
            workspace_manager: Pre-configured WorkspaceManager for this session.
            dispatcher: The process-wide SignalDispatcher; ``SignalPeer``
                registers this session for cross-peer fan-out.
        """
        super().__init__(dispatcher)

        self.app_state: "IAppState" = app_state
        self.workspace_manager: WorkspaceManager = workspace_manager

        self.context = SessionContext(session_id=self.session_id, app=app_state)
        self.context.session = self

        logger.info(f"Session created: {self.session_id}")

    @property
    def session_id(self) -> str:
        """This session's id — an alias of ``SignalPeer.peer_id``.

        The rest of the framework keys on this name: ``SessionManager``'s
        registry, ``LibraryStateContainer``'s per-session bags, presence,
        eviction. One identity under two names.
        """
        return self.peer_id

    def cleanup(self) -> None:
        """Tear down per-session state.

        Leaves the fan-out and drops every subscription (both from
        ``SignalPeer``). AppShell teardown is driven upstream by
        ``studio.app.on_disconnect`` — Session is not involved in chrome cleanup.
        """
        super().cleanup()
        logger.info(f"Session cleaned up: {self.session_id}")
