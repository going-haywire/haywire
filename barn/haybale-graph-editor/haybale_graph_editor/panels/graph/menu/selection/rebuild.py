from haywire.core.session.context import SessionContext

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.layout import PanelLayout

from haybale_graph_editor.panels._gating import is_reroute_node
from haybale_graph_editor.panels.graph.menu.selection.selection import (
    _selection_counts,
    _selection_nonempty,
    selection_label,
)
from haybale_graph_editor.surfaces import SelectionActions, SelectionMenu, SelectionRebuildMenu


@panel(
    surface=SelectionMenu,
    hosts=(SelectionRebuildMenu,),
    label="Rebuild",
    icon=hui.icon.refresh,
    order=80,
)
class RebuildSelectionMenuPanel(BasePanel):
    """The "Rebuild" row — a submenu over redraw / revalidate / reset.

    A hosting panel, so it draws only the arrangement: the row and the flyout
    it expands into. It pipes — the three commands inside reach the same
    ``SelectionActions`` host one hop further without either side naming it.
    """

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        if is_reroute_node(ctx):
            return False
        return _selection_nonempty(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.submenu_row("Rebuild", icon=hui.icon.refresh):
                self.render_surface(SelectionRebuildMenu, ctx)

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — a row that does not expand."""
        if is_reroute_node(ctx) is False:
            with layout:
                with layout:
                    hui.submenu_row("Rebuild", icon=hui.icon.refresh, enabled=False)


@panel(
    surface=SelectionRebuildMenu,
    label="Redraw Selection",
    icon=hui.icon.refresh,
    order=10,
)
class RedrawSelectionMenuPanel(BasePanel):
    """Redraw every node/edge in the selection in one step."""

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_nonempty(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        n_nodes, n_edges = _selection_counts(ctx)
        with layout:
            hui.menu_row(
                selection_label("Redraw", n_nodes, n_edges),
                icon=hui.icon.refresh,
                on_click=self.actions.redraw_selection,
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — what the row should say with nothing selected."""
        with layout:
            hui.menu_row("Redraw", icon=hui.icon.refresh, enabled=False)


@panel(
    surface=SelectionRebuildMenu,
    label="Revalidate Selection",
    icon=hui.icon.node_status,
    order=20,
)
class RevalidateSelectionMenuPanel(BasePanel):
    """Revalidate every node/edge in the selection in one step."""

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_nonempty(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        n_nodes, n_edges = _selection_counts(ctx)
        with layout:
            hui.menu_row(
                selection_label("Revalidate", n_nodes, n_edges),
                icon=hui.icon.node_status,
                on_click=self.actions.revalidate_selection,
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — what the row should say with nothing selected."""
        with layout:
            hui.menu_row("Revalidate", icon=hui.icon.node_status, enabled=False)


@panel(
    surface=SelectionRebuildMenu,
    label="Reset Selection",
    icon=hui.icon.reset,
    order=30,
)
class ResetSelectionMenuPanel(BasePanel):
    """Reset every node/edge in the selection in one step."""

    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _selection_nonempty(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        n_nodes, n_edges = _selection_counts(ctx)
        with layout:
            hui.menu_row(
                selection_label("Reset", n_nodes, n_edges),
                icon=hui.icon.reset,
                on_click=self.actions.reset_selection,
            )

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — what the row should say with nothing selected."""
        with layout:
            hui.menu_row("Reset", icon=hui.icon.reset, enabled=False)
