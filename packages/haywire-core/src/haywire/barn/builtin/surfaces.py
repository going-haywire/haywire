"""Surfaces declared by the built-in library.

``CanvasSettings`` is the *inspector* half of the old ``CanvasFocus``. Its
menu half moved into the graph editor's ``GraphContext`` and its regions, so
the canvas right-click menu no longer shares an id with the canvas properties
tab. Note that ``CanvasSettings`` sits one import away from the *panel*
``CanvasSettingsPanel`` that lives on it — they are deliberately kept in
different modules so the two names never appear in the same file.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from haywire.ui.surface import Presentation, Surface


class AppSettings(Surface):
    """Application-wide settings tab."""

    id = "app"
    order = 10
    presentation = Presentation(label="Application", icon="home")


class ExecutionInspector(Surface):
    """Execution settings tab."""

    id = "execution"
    order = 20
    presentation = Presentation(label="Execution", icon="rocket_launch")


class CanvasSettings(Surface):
    """Canvas & node appearance settings tab."""

    id = "canvas"
    order = 30
    presentation = Presentation(label="Canvas & Nodes", icon="grid_on")


@runtime_checkable
class AccountActions(Protocol):
    """What an account-menu panel may ask the host to do."""

    def logout(self) -> None: ...

    def reveal(self, editor_cls: type, binding_id: Any, label: str) -> None: ...


class AccountMenu(Surface):
    """The menu behind the ``account_circle`` icon in the ACTION bar footer.

    Always applies — its entries are access-filtered by the shared panel
    gate, and a menu whose tree draws nothing does not open at all. So a
    principal with no entries simply gets no menu, with no special case here.

    Not to be confused with ``AccountMenuProvider``, the host that opens it.
    """

    id = "account"
    order = 10
    provides = AccountActions
