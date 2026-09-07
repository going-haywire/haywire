# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/port/port.py
"""
Pin context-menu panels — the surface ``PinMenu``.

Reached structurally now: the canvas detects a pin from ``data-pin-id``,
which ``render_pin`` emits on every pin from every skin, so every skin gains
this menu and none can suppress it. Every panel below is safe under that:
the "Edit…" rows are read-only navigation, and the demote verb polls true
only on a promoted inlet.

"Edit…" holds the components behind the pin — its data type, and the widget
editing its value — and the selection menu carries the same submenu over its
own subjects, so one gesture answers "what is this made of" everywhere. See
``..component_rows`` for why those rows are not gated on developer mode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from ..component_rows import component_row, identity_of, key_and_label
from .....surfaces import PinEditMenu, PinMenu, PortActions
from .....state.edit_state import EditState


if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def _type_identity(ctx: "SessionContext") -> Any | None:
    """The identity of the active pin's data type, or None."""
    port = ctx.data[EditState].active_port
    if port is None:
        return None
    return identity_of(port.stored_type)


def _widget_identity(ctx: "SessionContext") -> Any | None:
    """The identity of the widget editing the active pin, or None.

    ``widget_key`` is resolved through the global widget registry rather than
    trusted: a key naming a widget that is not installed resolves to None, as
    does a port with no widget at all (an outlet, or an inlet whose type
    carries no editor).
    """
    from haywire.ui.widget.globals import get_widget_class

    port = ctx.data[EditState].active_port
    if port is None or not port.widget_key:
        return None
    return identity_of(get_widget_class(port.widget_key))


@panel(
    surface=PinMenu,
    hosts=(PinEditMenu,),
    label="Edit",
    icon=hui.icon.node_source,
    order=10,
)
class PinEditMenuPanel(BasePanel):
    """The "Edit…" row — a submenu over the components behind this pin.

    A hosting panel: it draws only the row and the flyout, and pipes the
    ``PortActions`` host one hop further to the rows inside. Mirrors
    ``DetailSelectionMenuPanel``, which does the same for the detail ranks.

    **The rows inside must be their own panels, not inline ``hui.menu_row``
    calls.** The leaf counter that decides whether a ``hui.submenu_row`` greys
    itself is bumped by ``render_panel`` — once per panel — and by nothing
    else; ``hui.menu_row`` does not touch it. Drawing the rows inline
    therefore leaves the body's count at 0, and ``SubmenuRow.__exit__`` greys
    the anchor retroactively: a fully populated flyout that cannot be opened
    (``hw-disabled``, ``pointer-events: none``), with nothing in the DOM to
    say why.
    """

    actions: PortActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _type_identity(ctx) is not None or _widget_identity(ctx) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.submenu_row("Edit", icon=hui.icon.node_source):
                self.render_surface(PinEditMenu, ctx)


@panel(
    surface=PinEditMenu,
    label="Type",
    icon=hui.icon.type,
    order=10,
)
class PortTypeMenuPanel(BasePanel):
    """The pin's data type, as a row that opens the type's source."""

    actions: PortActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _type_identity(ctx) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        port = ctx.data[EditState].active_port
        fallback = getattr(port.stored_type, "__name__", "") if port is not None else ""
        key, label = key_and_label(_type_identity(ctx), fallback)
        with layout:
            component_row(ctx, label, key, hui.icon.type)


@panel(
    surface=PinEditMenu,
    label="Widget",
    icon=hui.icon.widget,
    order=20,
)
class PortWidgetMenuPanel(BasePanel):
    """The widget editing this pin, as a row that opens the widget's source.

    Polls false on a port with no widget, so the row never advertises a
    component that isn't there.
    """

    actions: PortActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _widget_identity(ctx) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        key, label = key_and_label(_widget_identity(ctx))
        with layout:
            component_row(ctx, label, key, hui.icon.widget)


@panel(
    surface=PinMenu,
    label="Detach from setting",
    icon=hui.icon.delete,
    order=30,
)
class DetachSettingMenuPanel(BasePanel):
    """Enabled only on a promoted inlet; demotes it back to a plain setting.

    On any other pin it greys rather than disappearing — the platform
    convention every panel on ``SelectionMenu`` already follows, and here it
    is also load-bearing. This is ``PinMenu``'s only **leaf**: the "Edit" row
    beside it is a hosting panel, and a hosting panel is deliberately
    excluded from the popup's leaf count (ADR-0029, and the leaf counter is
    reset per flyout level, so what the submenu body draws never reaches the
    popup's own count). Were this panel to vanish on an unpromoted pin, the
    popup would render with zero leaves and be deleted — **no pin menu at
    all**, on the great majority of pins, taking the edge-drag resume that
    rides on its close with it. ``draw_disabled`` is what keeps the count at
    one. See ``.insights/project_surface_popup_emptiness_contract.md``.
    """

    actions: PortActions

    _LABEL = "Detach from setting"

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        port = ctx.data[EditState].active_port
        return port is not None and port.promoted

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        port = ctx.data[EditState].active_port
        if port is None:
            return
        with layout:
            hui.menu_row(
                self._LABEL,
                icon=hui.icon.delete,
                on_click=lambda: self.actions.demote_setting(port.id),
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The greyed form, on a pin that was never promoted."""
        with layout:
            hui.menu_row(self._LABEL, icon=hui.icon.delete, enabled=False)
