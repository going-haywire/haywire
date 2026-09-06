"""Account-menu panels — behind the account_circle icon in the ACTION bar footer.

These are ordinary panels on ``AccountMenu``, so the shared panel gate filters
them by ``access=`` with no special case, and the menu does not open at all
when a principal has nothing in it.
"""

from __future__ import annotations

from nicegui import ui

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


@panel(
    surface=AccountMenu,
    label="Developer mode",
    order=50,
    access=AccessTier.VIEW,
)
class DeveloperModePanel(BasePanel):
    """Toggles ``ctx.developer_mode`` for THIS session.

    Developer mode reveals affordances that expose the studio's own
    implementation rather than the user's graph — a settings row's "open this
    bag's source" entry, for one. It belongs on the account menu rather than
    the Debug settings tab because it is session state, not a stored setting:
    every panel on ``DebugSurface`` renders a persisted registry value through
    ``render_schema``, so a switch that vanishes on restart would be the one
    control there a user reasonably expects to stick.

    VIEW rather than EDIT: the flag only decides whether an affordance is
    drawn, never whether it may be used. Opening a component's source still
    goes through the editor's own access check, and ComponentSourceEditor
    refuses to write a non-editable library regardless — so gating the toggle
    higher would hide a read-only view from the principals most likely to want
    it, and buy no safety.

    The row does not close the menu, so the checkmark is the only feedback a
    click gives and it has to move under the pointer. The menu is rebuilt on
    every open (see BaseContextMenuProvider._open_menu), but that only fixes
    the state on the NEXT open — the row already on screen is a drawn element
    nothing redraws, so the icon is swapped in place here. Same pattern, and
    the same defensive child lookup, as SelectionCollapsePanel's expand/
    collapse row in haybale-graph-editor.
    """

    actions: AccountActions

    @classmethod
    def poll(cls, ctx) -> bool:
        return True

    @staticmethod
    def _row_icon(enabled: bool) -> str:
        return hui.icon.checked if enabled else hui.icon.unchecked

    def draw(self, ctx, layout) -> None:
        with layout:
            row = hui.menu_row(
                "Developer mode",
                icon=self._row_icon(ctx.developer_mode),
                tooltip="Show affordances that open the studio's own source",
            )

        # Reach into the row just built to re-icon it after a click. menu_row's
        # shape is (icon?, label) and it always makes both here, since an icon
        # was passed — but read it defensively rather than by index, so a change
        # to that shape degrades to "the row stops updating" instead of raising
        # out of a click handler.
        icon_el = next((c for c in row.default_slot.children if isinstance(c, ui.icon)), None)

        def _toggle() -> None:
            now_enabled = not ctx.developer_mode
            ctx.developer_mode = now_enabled
            if icon_el is not None:
                icon_el.set_name(self._row_icon(now_enabled))

        row.on("click", lambda _e=None: _toggle())
