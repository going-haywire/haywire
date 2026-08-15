from __future__ import annotations

from haywire.core.session.context import SessionContext
from haywire.ui.panel.focus import Focus


class AppFocus(Focus):
    id = "app"
    label = "Application"
    icon = "home"
    order = 10

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return True


class ExecutionFocus(Focus):
    id = "execution"
    label = "Execution"
    icon = "rocket_launch"
    order = 20

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return True


class CanvasFocus(Focus):
    id = "canvas"
    label = "Canvas & Nodes"
    icon = "grid_on"
    order = 30

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return True


class AccountFocus(Focus):
    """The account menu behind the ``account_circle`` icon in the ACTION bar footer.

    Always available — the menu itself is access-filtered by
    ``visible_panels()``, and ``_open_menu`` refuses to open when nothing is
    visible. So a principal with no entries simply gets no menu, with no
    special case here.
    """

    id = "account"
    label = "Account"
    icon = "account_circle"
    order = 10

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return True
