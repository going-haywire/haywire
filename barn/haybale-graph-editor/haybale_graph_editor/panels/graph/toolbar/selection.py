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

from nicegui import ui

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
    label="Collapse",
    icon=hui.icon.node_collapse,
    order=25,
)
class CollapseToolbarPanel(BasePanel):
    """One button that folds or unfolds the selection (ADR 0032).

    The same verb as the context menu's Collapse row, on the toolbar because
    folding is the gesture a user repeats while reading a graph — the
    code-folding idiom — and a repeated gesture should not cost a right-click.

    Like that row, it decides nothing at draw time: ``toggle_selection_collapsed``
    reads the current state per click and returns the new one, and the button
    restyles itself from the answer. The toolbar usually re-renders anyway
    (folding changes a node's size, which moves the selection bounds that
    position it), but "usually" is not a thing to leave a toggle resting on.

    The icon names the ACTION, matching the tooltip — never the current state,
    which would contradict the words beside it.
    """

    actions: SelectionActions

    @staticmethod
    def _icon(collapsed: bool) -> str:
        return hui.icon.node_expand if collapsed else hui.icon.node_collapse

    @staticmethod
    def _tip(collapsed: bool) -> str:
        return "Expand" if collapsed else "Collapse"

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        collapsed = self.actions.selection_is_collapsed()

        with layout:
            # Tooltip built here rather than through icon_action's `tooltip=`
            # so there is a handle to retext: that helper's tooltip is created
            # and forgotten, and calling `.tooltip()` again would stack a
            # second one rather than replace the first.
            btn = hui.icon_action(self._icon(collapsed))
            with btn:
                tip = ui.tooltip(self._tip(collapsed))

        def _toggle() -> None:
            now = self.actions.toggle_selection_collapsed()
            btn.props(f"icon={self._icon(now)}")
            btn.update()
            tip.set_text(self._tip(now))

        btn.on("click", lambda _e=None: _toggle())


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
