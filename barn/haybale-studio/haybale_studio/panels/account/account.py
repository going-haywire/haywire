"""Account-menu panels — behind the account_circle icon in the ACTION bar footer.

These are ordinary panels on ``AccountMenu``, so the shared panel gate filters
them by ``access=`` with no special case, and the menu does not open at all
when a principal has nothing in it.
"""

from __future__ import annotations

from haywire.barn.builtin.surfaces import AccountActions, AccountMenu
from haywire.core.access import AccessTier
from haywire.ui import elements as hui
from haywire.ui.panel.base import BasePanel
from haywire.ui.panel.decorator import panel


@panel(
    surface=AccountMenu,
    label="Sign out",
    order=90,
    access=AccessTier.VIEW,
)
class LogoutPanel(BasePanel):
    """Ends this browser session. Hidden entirely when authentication is off."""

    actions: AccountActions

    @classmethod
    def poll(cls, ctx) -> bool:
        return ctx.principal is not None

    def draw(self, ctx, layout) -> None:
        with layout:
            hui.menu_row("Sign out", icon="logout", on_click=self.actions.logout)


@panel(
    surface=AccountMenu,
    label="Manage principals",
    order=10,
    access=AccessTier.ADMIN,
)
class OpenRosterPanel(BasePanel):
    """Opens the RosterEditor. Admin-only, so a view principal never sees it."""

    actions: AccountActions

    @classmethod
    def poll(cls, ctx) -> bool:
        return True

    def draw(self, ctx, layout) -> None:
        from haybale_studio.editors.roster_editor import RosterEditor

        with layout:
            hui.menu_row(
                "Manage accounts",
                icon="manage_accounts",
                on_click=lambda: self.actions.reveal(RosterEditor, None, RosterEditor.class_identity.label),
            )


@panel(
    surface=AccountMenu,
    label="Sign everyone out",
    order=80,
    access=AccessTier.ADMIN,
)
class RotateSecretPanel(BasePanel):
    """Rotates the cookie signing secret and evicts every live session.

    The panic lever: one action that invalidates every issued cookie at once,
    for when a laptop goes missing rather than when one principal leaves.
    """

    actions: AccountActions

    @classmethod
    def poll(cls, ctx) -> bool:
        return ctx.principal is not None

    def draw(self, ctx, layout) -> None:
        with layout:
            hui.menu_row("Sign everyone out", icon="logout", on_click=self._rotate)

    def _rotate(self) -> None:
        from haywire_studio.auth.cookies import rotate_secret
        from haywire_studio.auth.eviction import evict_all

        rotate_secret()
        evict_all(self._session_manager())
        self.actions.logout()

    @staticmethod
    def _session_manager():
        from haywire.core.di.context import get_session_manager

        return get_session_manager()


@panel(
    surface=AccountMenu,
    label="Agent activity",
    order=20,
    access=AccessTier.VIEW,
)
class OpenActivityPanel(BasePanel):
    """Opens the ActivityEditor.

    The entry point lives here rather than on the TopBar's agent chip: the chip
    is core's (``haywire.ui.app.shell``) and the editor is this library's, so a
    chip click could only reach it by resolving a registry key hardcoded in
    core — a dependency pointing the wrong way. A panel against
    ``AccountMenu`` inverts it: the library that owns the editor is also the
    one that names it, and core stays unaware the editor exists.

    VIEW access matches the editor's own: what the agents in this studio are
    doing is useful to every collaborator.
    """

    actions: AccountActions

    @classmethod
    def poll(cls, ctx) -> bool:
        return True

    def draw(self, ctx, layout) -> None:
        from haybale_studio.editors.activity_editor import ActivityEditor

        with layout:
            hui.menu_row(
                "Agent activity",
                icon="smart_toy",
                on_click=lambda: self.actions.reveal(
                    ActivityEditor, None, ActivityEditor.class_identity.label
                ),
            )
