"""The account menu provider (ADR 0027).

Reuses ``BaseContextMenuProvider`` rather than hand-rolling a popup, which buys
three things for free: entries are access-filtered by the shared panel gate, the
menu refuses to open when nothing draws, and libraries can contribute their own
account entries by registering a panel against :class:`AccountMenu`.

The provider keeps its name; the *surface* it opens is ``AccountMenu``, which
lives with its Protocol in ``haywire.barn.builtin.surfaces``.
"""

from __future__ import annotations

from typing import Any, Tuple

from haywire.barn.builtin.surfaces import AccountActions, AccountMenu
from haywire.ui.panel.context_menu_base import BaseContextMenuProvider

__all__ = ["AccountActions", "AccountMenuProvider"]


class AccountMenuProvider(BaseContextMenuProvider):
    """Opens :class:`AccountMenu` and satisfies :class:`AccountActions`."""

    def open(self, pos: Tuple[float, float]) -> None:
        """Show the menu at ``pos``, or nothing if this principal has no entries."""
        self._open_menu(AccountMenu, pos)

    # -- AccountActions -------------------------------------------------

    def logout(self) -> None:
        """POST to ``/logout`` so the server clears the cookie, then reload.

        A form POST rather than a link because the cookie is ``HttpOnly`` —
        the browser cannot clear it from JavaScript, only the server can.
        """
        self._run_js("fetch('/logout', {method: 'POST'}).then(() => window.location.href = '/login')")
        if self._open_popup is not None:
            self._open_popup.close()

    def reveal(self, editor_cls: type, binding_id: Any, label: str) -> None:
        from haywire.core.signals import Reveal

        self._session.publish(Reveal(editor=editor_cls, binding_id=binding_id, label=label))
        if self._open_popup is not None:
            self._open_popup.close()

    @staticmethod
    def _run_js(script: str) -> None:
        """Seam for tests — production goes straight to NiceGUI."""
        from nicegui import ui

        ui.run_javascript(script)
