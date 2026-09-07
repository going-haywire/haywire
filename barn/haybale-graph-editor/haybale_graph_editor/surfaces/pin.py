"""The pin right-click menu.

Reached structurally: ``render_pin`` emits ``data-pin-id`` on every pin from
every skin, so the canvas detects a pin the same way it detects a node or an
edge, and *which* surface a pin opens is the framework's decision rather than
the skin's. A skin no longer decides whether a pin has a menu at all, and
cannot suppress the built-in one (ADR-0029, Routing).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from haywire.ui.surface import Surface

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@runtime_checkable
class PortActions(Protocol):
    """Verbs available when the user right-clicks a pin.

    Carries one real verb: the demote backing "Detach from setting", shown
    only on a promoted inlet.
    """

    def demote_setting(self, port_id: str) -> None: ...


class PinMenu(Surface):
    """The pin right-click menu."""

    id = "pin"
    provides = PortActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        from haybale_graph_editor.state.edit_state import EditState

        return ctx.data[EditState].active_port is not None


class PinEditMenu(Surface):
    """The "Edit…" submenu of ``PinMenu`` — the components behind this pin.

    One row per component that produced what the user is looking at: the
    pin's data type, and the widget editing its value. Both open that
    component's source, so the submenu answers "what is this made of, and
    where is its code" in one place instead of spending two top-level rows.

    The selection menu carries the same submenu over its own subjects (node,
    skin, theme), so the gesture reads identically wherever the user
    right-clicks.

    Declares no ``poll`` for the same reason ``SelectionDetailMenu`` does not
    — the hosting panel already gates on the active port, and a second copy
    of that predicate would swallow the greyed rows.
    """

    id = "pin-edit"
    provides = PortActions
