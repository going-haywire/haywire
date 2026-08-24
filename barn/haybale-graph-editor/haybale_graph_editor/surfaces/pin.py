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
