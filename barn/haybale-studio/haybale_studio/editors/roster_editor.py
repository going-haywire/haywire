"""RosterEditor — add, remove, re-tier and re-key principals.

Admin-only, and reached through the account menu rather than a bar tab: it is a
standing list you open deliberately, not something tied to the current
selection. All mutations go through ``haywire_studio.auth.operations`` so the
UI and the CLI enforce exactly one set of rules.
"""

from __future__ import annotations

from haywire.core.access import AccessTier
from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire_studio.auth.operations import (
    add_agent,
    add_user,
    remove_principal,
    set_password,
    set_tier,
)
from haywire_studio.security.document import load_document
from haywire_studio.security.errors import SecurityError
from nicegui import ui


@editor(
    label="Principals",
    icon="manage_accounts",
    default_slot="edit",
    opens="on_context",
    description="Manage who may reach this studio",
    access=AccessTier.ADMIN,
)
class RosterEditor(BaseEditor):
    """The roster table plus add/remove/re-tier controls."""

    def draw(self, context, container) -> None:
        container.clear()
        with container:
            with ui.column().classes("w-full gap-4 p-4"):
                self._draw_roster()
                self._draw_add_form()

    # -- table ----------------------------------------------------------

    def _draw_roster(self) -> None:
        try:
            document = load_document()
            roster = document.auth
        except SecurityError as exc:
            hui.error_label(f"Roster unreadable: {exc}")
            return

        state = "enabled" if roster.enabled else "disabled"
        hui.section_label(f"Authentication is {state}")
        if not roster.enabled:
            ui.label("Run 'haywire auth enable' with the studio stopped to require a login.").classes(
                "hw-text-muted text-xs"
            )

        for principal in roster.principals:
            self._draw_row(principal)

    def _draw_row(self, principal) -> None:
        with ui.row().classes("w-full items-center gap-2 hw-panel p-2"):
            ui.icon("smart_toy" if principal.is_agent else "person")
            ui.label(principal.name).classes("font-medium")

            tier_select = ui.select([tier.value for tier in AccessTier], value=principal.tier.value).props(
                "dense outlined"
            )
            tier_select.on(
                "update:modelValue",
                lambda event, name=principal.name: self._set_tier(name, event.args),
            )

            if principal.is_agent:
                hui.code_snippet(principal.token)
            else:
                ui.button(icon="key", on_click=lambda name=principal.name: self._ask_password(name)).props(
                    "flat dense round"
                ).tooltip("Set password")

            ui.button(icon="delete", on_click=lambda name=principal.name: self._remove(name)).props(
                "flat dense round"
            ).tooltip("Remove")

    # -- mutations ------------------------------------------------------

    def _set_tier(self, name: str, value) -> None:
        try:
            set_tier(name, AccessTier(value))
        except (SecurityError, ValueError) as exc:
            ui.notify(str(exc), type="negative")
            return
        ui.notify(f"{name} is now {value}")
        self.wrapper.redraw()

    def _remove(self, name: str) -> None:
        """Remove a principal and evict their live sessions immediately.

        Eviction is the half that makes this a revocation rather than a request:
        the gate cannot revoke an already-open websocket, so removal pushes.
        """
        from haywire.core.di.context import get_session_manager

        from haywire_studio.auth.eviction import evict_principal

        try:
            remove_principal(name)
        except SecurityError as exc:
            ui.notify(str(exc), type="negative")
            return

        evicted = evict_principal(get_session_manager(), name)
        ui.notify(f"Removed {name} ({evicted} session(s) ended)")
        self.wrapper.redraw()

    def _ask_password(self, name: str) -> None:
        with ui.dialog() as dialog, hui.dialog_card():
            field = ui.input("New password", password=True).classes("w-full")
            hui.dialog_actions(
                on_confirm=lambda: self._set_password(dialog, name, field.value),
                on_cancel=dialog.close,
            )
        dialog.open()

    def _set_password(self, dialog, name: str, value: str) -> None:
        try:
            set_password(name, value or "")
        except SecurityError as exc:
            ui.notify(str(exc), type="negative")
            return
        dialog.close()
        ui.notify(f"Password updated for {name}")

    # -- add form -------------------------------------------------------

    def _draw_add_form(self) -> None:
        hui.section_label("Add a principal")
        with ui.row().classes("w-full items-end gap-2"):
            name = ui.input("Name").props("dense outlined")
            tier = ui.select([t.value for t in AccessTier], value=AccessTier.VIEW.value).props(
                "dense outlined"
            )
            kind = ui.select(["user", "agent"], value="user").props("dense outlined")
            password = ui.input("Password", password=True).props("dense outlined")
            ui.button(
                "Add",
                on_click=lambda: self._add(name.value, kind.value, tier.value, password.value),
            ).props("flat dense")

    def _add(self, name: str, kind: str, tier: str, password: str) -> None:
        try:
            if kind == "agent":
                agent = add_agent(name, AccessTier(tier))
                ui.notify(f"Created agent {agent.name} — copy its token from the list")
            else:
                add_user(name, password or "", AccessTier(tier))
                ui.notify(f"Created user {name}")
        except (SecurityError, ValueError) as exc:
            ui.notify(str(exc), type="negative")
            return
        self.wrapper.redraw()
