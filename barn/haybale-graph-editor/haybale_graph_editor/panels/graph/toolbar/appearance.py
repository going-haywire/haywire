# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/toolbar/appearance.py
"""
The toolbar's Appearance dropdown — the surface ``NodeAppearance``.

Two panels, one per side of the nesting: ``AppearanceToolbarPanel`` is the
icon on ``SelectionToolbar`` that hosts the surface, and
``NodeAppearancePanel`` is what lands inside it.

A *dropdown*, not a flyout: what hangs below is a stack of editable fields,
not a list of commands. ``hui.dropdown`` opens on click and never
``auto-close``s, because a menu's auto-close dismisses on any click inside it
— the first click into a field would shut the panel. See
``haywire.ui.elements.flyout.DropdownIcon``.

The fields are the *live* ``appearance`` category of the node's own props bag
(``skin``, ``layout_direction``, ``body_color``, ``border_color``,
``border_thickness``, ``border_roundness``) — the same rows, the same
reset chrome and the same subscriptions the properties editor renders, sliced
by ``render_settings(categories=...)`` rather than copied. Editing one here
and in the Node Properties panel is the same write.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_settings

from ....surfaces import NodeAppearance, SelectionActions, SelectionToolbar
from ....state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext

# The one category of NodeProperties this surface owns. Declared once here so
# the panel and its tests cannot disagree about which slice is on show.
APPEARANCE_CATEGORY = "appearance"


def _appearance_bag(ctx: "SessionContext") -> Any | None:
    """The active node's props bag, or None when there is no node to style."""
    wrapper = ctx.data[EditState].active_node
    if wrapper is None:
        return None
    node = getattr(wrapper, "node", None)
    return getattr(node, "props", None)


@panel(
    surface=SelectionToolbar,
    hosts=(NodeAppearance,),
    label="Appearance",
    icon=hui.icon.theme,
    order=30,
)
class AppearanceToolbarPanel(BasePanel):
    """The ⧉ icon that drops the appearance fields below the toolbar.

    Unlike its neighbours it *does* declare a ``poll``: ``SelectionToolbar``
    gates on "something is selected", which an edges-only selection satisfies,
    and there is nothing to style without a node.

    It pipes, like every other hosting panel here — ``NodeAppearance``
    declares no ``provides``, so the host travels on unexamined.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _appearance_bag(ctx) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.dropdown(hui.icon.theme, tooltip="Appearance", align="center", direction="up"):
                self.render_surface(NodeAppearance, ctx)


@panel(
    surface=NodeAppearance,
    label="Node Appearance",
    icon=hui.icon.theme,
    order=10,
)
class NodeAppearancePanel(BasePanel):
    """The appearance slice of the active node's props bag, live-editable.

    Scoped to the primary (active) node, like ``NodeErrorsSelectionMenuPanel``:
    ``EditState.active_node`` is the selection's primary, so a multi-node
    selection styles the one that was right-clicked rather than silently
    editing several bags.

    The ``hw-panel`` wrapper is load-bearing. A dropdown is a ``QMenu`` and
    portals to ``<body>``, outside the toolbar popup's own ``hw-panel``, so
    without it every ``.hw-panel``-scoped field rule in the shell CSS misses
    these rows — the same portal trap that gave menus three different colours.
    """

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _appearance_bag(ctx) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        bag = _appearance_bag(ctx)
        if bag is None:
            return
        with layout:
            with ui.column().classes("hw-panel gap-0").style("min-width: 240px"):
                render_settings(bag, categories=(APPEARANCE_CATEGORY,))
