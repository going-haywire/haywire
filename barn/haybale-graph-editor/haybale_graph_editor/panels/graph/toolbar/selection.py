# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/toolbar/selection.py
"""
Floating-toolbar panels for the graph canvas — the surface ``SelectionToolbar``.

Each panel contributes a single icon-only button; the provider owns the
``ui.row`` container.

Copy and Delete declare no ``poll``: ``SelectionToolbar.poll`` is exactly
"something is selected", the host gates it once before querying, and the
shared filter does not re-check it — so restating the surface's predicate on
each panel would be a second place to keep in sync for no behaviour.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from ....surfaces import SelectionActions, SelectionMenu, SelectionToolbar

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=SelectionToolbar,
    label="Copy",
    icon=hui.icon.copy,
    order=10,
)
class CopyToolbarPanel(BasePanel):
    actions: SelectionActions

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.icon_action(hui.icon.copy, tooltip="Copy", on_click=self.actions.copy_selection)


@panel(
    surface=SelectionToolbar,
    label="Delete",
    icon=hui.icon.delete,
    order=20,
)
class DeleteToolbarPanel(BasePanel):
    actions: SelectionActions

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            hui.icon_action(hui.icon.delete, tooltip="Delete", on_click=self.actions.delete_selection)


@panel(
    surface=SelectionToolbar,
    hosts=(SelectionMenu,),
    label="More",
    icon="more_horiz",
    order=999,
)
class SelectionOverflowPanel(BasePanel):
    """The ⋯ — a panel that hosts the selection right-click menu.

    It renders ``SelectionMenu`` itself rather than round-tripping a
    synthetic event through the canvas to reopen it, so the batch ops live in
    one place: the flyout shows the *same panel classes* the right-click menu
    yields, not a duplicated curated set, and nothing moved off the menu.

    It pipes — the default. ``SelectionToolbarProvider`` satisfies
    ``SelectionActions``, so the host it received travels one hop further.
    """

    actions: SelectionActions

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.flyout("more_horiz", tooltip="More actions"):
                self.render_surface(SelectionMenu, ctx)
