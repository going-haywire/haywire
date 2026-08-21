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

    Signal mechanics live on :class:`~haywire.core.signals.peer.SignalPeer`:
    ``publish`` / ``subscribe`` / ``_dispatch`` / ``cleanup``, plus membership
    in the :class:`~haywire.core.signals.dispatcher.SignalDispatcher` fan-out.
    A Session is one *kind* of peer — the browser-tab kind — adding exactly
    three things a bare peer has not: a ``SessionContext``, a
    ``WorkspaceManager``, and a reference to the shared app state.

    Editors auto-wire their ``@redraw_on`` / ``@react_on`` decorated methods at
    instantiation; panels contribute signal types via ``redraw_on=`` on
    ``@panel(...)``; the AppShell subscribes its workspace-mutation handlers
    (``Reveal``, ``Close``) directly. Signals whose ``cross_session`` is True
    travel to every registered peer through the dispatcher — including
    non-browser peers, which is how an agent-facing host observes changes that
    originated in a browser tab.
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
            dispatcher: The process-wide SignalDispatcher. Handed to
                ``SignalPeer``, which registers this session for cross-peer
                fan-out. Replaces the former ``session_manager`` argument —
                a session needs a channel to broadcast on, not a registry of
                its siblings.
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

        Kept under the name the rest of the framework already uses:
        ``SessionManager`` keys its registry by it, ``LibraryStateContainer``
        bags per-session state by it, presence and eviction read it. One
        identity under two names — a session's peer identity *is* its session
        identity, so they must never diverge.
        """
        return self.peer_id

    def cleanup(self) -> None:
        """Tear down per-session state.

        Leaves the dispatcher fan-out and drops every signal-bus subscription
        (both inherited from ``SignalPeer``). AppShell teardown is driven
        upstream by studio.app.on_disconnect (Q7A: shell-upstream model) —
        Session is not involved in chrome cleanup.
        """
        super().cleanup()
        logger.info(f"Session cleaned up: {self.session_id}")
