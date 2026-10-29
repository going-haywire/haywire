"""The "Layout" and "Select" rows of the selection menu, over the flow verbs of the selected nodes.

The selected nodes are the start nodes. Layout lays out their flow, or the nodes downstream or
upstream of a single start node, keeping a single start node in place; Arrange Flow also takes
several, arranging every flow they touch. Select needs exactly one node and selects the nodes
downstream or upstream of it. Layout also turns the layout of two or more selected nodes a quarter
turn, to follow a change of the graph's layout direction. Both need EDIT. See
``haywire.core.graph.arrange``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from haywire.core.graph.arrange import ArrangeScope
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.layout import PanelLayout

from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.surfaces import (
    SelectionActions,
    SelectionLayoutMenu,
    SelectionMenu,
    SelectionSelectMenu,
)

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def _start_node(ctx: "SessionContext") -> Optional[str]:
    """The id of the one selected node, if it exists in the active graph and no edge is selected."""
    edit = ctx.data[EditState]
    graph = edit.active_graph
    if graph is None or len(edit.selected_nodes) != 1 or edit.selected_edges:
        return None
    (node_id,) = edit.selected_nodes
    return node_id if graph.get_node_wrapper(node_id) is not None else None


def _start_nodes(ctx: "SessionContext") -> list[str]:
    """The ids of the selected nodes that exist in the active graph, sorted."""
    edit = ctx.data[EditState]
    graph = edit.active_graph
    if graph is None:
        return []
    return sorted(n for n in edit.selected_nodes if graph.get_node_wrapper(n) is not None)


def _selection_nonempty(ctx: "SessionContext") -> bool:
    edit = ctx.data[EditState]
    return bool(edit.selected_nodes or edit.selected_edges)


# SelectionMenu
#  -> LayoutSelectionMenuPanel
#     -> SelectionLayoutMenu
#        -> ArrangeFlowMenuPanel
#        -> ArrangeDownstreamMenuPanel
#        -> ArrangeUpstreamMenuPanel
#        -> RotateClockwiseMenuPanel
#        -> RotateCounterClockwiseMenuPanel
#  -> SelectFlowSelectionMenuPanel
#     -> SelectionSelectMenu
#        -> SelectDownstreamMenuPanel
#        -> SelectUpstreamMenuPanel


class _FlowHostPanel(BasePanel):
    """A submenu row over the flow verbs; greys unless one node is selected."""

    actions: SelectionActions
    submenu: type
    row_label: str
    row_icon: str

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _start_node(ctx) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            with hui.submenu_row(self.row_label, icon=self.row_icon):
                self.render_surface(self.submenu, ctx)

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        """The static form, greyed — a row that does not expand."""
        if _selection_nonempty(ctx):
            with layout:
                hui.submenu_row(self.row_label, icon=self.row_icon, enabled=False)


class _FlowVerbPanel(BasePanel):
    """A menu row that applies one flow verb from the start node; greys for several nodes."""

    actions: SelectionActions
    scope: ArrangeScope
    row_label: str
    row_icon: str

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _start_node(ctx) is not None

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        node_id = _start_node(ctx)
        if node_id is None:
            return
        with layout:
            hui.menu_row(self.row_label, icon=self.row_icon, on_click=lambda: self._apply(node_id))

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        if _start_nodes(ctx):
            with layout:
                hui.menu_row(self.row_label, icon=self.row_icon, enabled=False)

    def _apply(self, node_id: str) -> None:
        raise NotImplementedError


class _ArrangeMenuPanel(_FlowVerbPanel):
    def _apply(self, node_id: str) -> None:
        self.actions.arrange_from([node_id], self.scope)


class _SelectMenuPanel(_FlowVerbPanel):
    def _apply(self, node_id: str) -> None:
        self.actions.select_from(node_id, self.scope)


@panel(
    surface=SelectionMenu,
    hosts=(SelectionLayoutMenu,),
    label="Layout",
    description='The "Layout" row: a submenu laying out the flow around the selected nodes.',
    icon=hui.icon.layout,
    order=422,
)
class LayoutSelectionMenuPanel(_FlowHostPanel):
    """The "Layout" row: a submenu laying out the flow around the selected nodes.

    A single selected node stays where it is; the nodes the verb covers are placed around it.
    Only Arrange Flow takes several nodes.
    """

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return bool(_start_nodes(ctx))

    submenu = SelectionLayoutMenu
    row_label = "Layout"
    row_icon = hui.icon.layout


@panel(
    surface=SelectionLayoutMenu,
    label="Arrange Flow",
    description="Lay out every node connected to the selected nodes.",
    icon=hui.icon.arrange_flow,
    order=10,
)
class ArrangeFlowMenuPanel(_ArrangeMenuPanel):
    """Lay out every node connected to this node, keeping this node in place.

    With several nodes selected, lays out every flow they touch, centred where it was.
    """

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return bool(_start_nodes(ctx))

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        node_ids = _start_nodes(ctx)
        if not node_ids:
            return
        with layout:
            hui.menu_row(
                self.row_label,
                icon=self.row_icon,
                on_click=lambda: self.actions.arrange_from(node_ids, self.scope),
            )

    scope = ArrangeScope.FLOW
    row_label = "Arrange Flow"
    row_icon = hui.icon.arrange_flow


@panel(
    surface=SelectionLayoutMenu,
    label="Arrange Downstream",
    description="Lay out the nodes downstream of this node, keeping this node in place.",
    icon=hui.icon.arrange_downstream,
    order=20,
)
class ArrangeDownstreamMenuPanel(_ArrangeMenuPanel):
    """Lay out the nodes downstream of this node, keeping this node in place."""

    scope = ArrangeScope.DOWNSTREAM
    row_label = "Arrange Downstream"
    row_icon = hui.icon.arrange_downstream


@panel(
    surface=SelectionLayoutMenu,
    label="Arrange Upstream",
    description="Lay out the nodes upstream of this node, keeping this node in place.",
    icon=hui.icon.arrange_upstream,
    order=30,
)
class ArrangeUpstreamMenuPanel(_ArrangeMenuPanel):
    """Lay out the nodes upstream of this node, keeping this node in place."""

    scope = ArrangeScope.UPSTREAM
    row_label = "Arrange Upstream"
    row_icon = hui.icon.arrange_upstream


@panel(
    surface=SelectionMenu,
    hosts=(SelectionSelectMenu,),
    label="Select",
    description='The "Select" row: a submenu selecting the nodes downstream or upstream of this node.',
    icon=hui.icon.select_flow,
    order=424,
)
class SelectFlowSelectionMenuPanel(_FlowHostPanel):
    """The "Select" row: a submenu selecting the nodes downstream or upstream of this node."""

    submenu = SelectionSelectMenu
    row_label = "Select"
    row_icon = hui.icon.select_flow


@panel(
    surface=SelectionSelectMenu,
    label="Select Downstream",
    description="Select every node downstream of this node, instead of this node.",
    icon=hui.icon.select_downstream,
    order=10,
)
class SelectDownstreamMenuPanel(_SelectMenuPanel):
    """Select every node downstream of this node, instead of this node."""

    scope = ArrangeScope.DOWNSTREAM
    row_label = "Select Downstream"
    row_icon = hui.icon.select_downstream


@panel(
    surface=SelectionSelectMenu,
    label="Select Upstream",
    description="Select every node upstream of this node, instead of this node.",
    icon=hui.icon.select_upstream,
    order=20,
)
class SelectUpstreamMenuPanel(_SelectMenuPanel):
    """Select every node upstream of this node, instead of this node."""

    scope = ArrangeScope.UPSTREAM
    row_label = "Select Upstream"
    row_icon = hui.icon.select_upstream


class _RotateMenuPanel(BasePanel):
    """A menu row that turns the layout of the selected nodes a quarter turn; needs two nodes."""

    actions: SelectionActions
    clockwise: bool
    row_label: str
    row_icon: str

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return len(_start_nodes(ctx)) >= 2

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        with layout:
            # The menu stays open, so the next turn is one more click.
            hui.menu_row(self.row_label, icon=self.row_icon, on_click=self._rotate, closes=False)

    def draw_disabled(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        if _start_nodes(ctx):
            with layout:
                hui.menu_row(self.row_label, icon=self.row_icon, enabled=False)

    def _rotate(self) -> None:
        self.actions.rotate_selection(self.clockwise)


@panel(
    surface=SelectionLayoutMenu,
    label="Rotate Clockwise",
    description="Turn the layout of the selected nodes a quarter turn clockwise, in place.",
    icon=hui.icon.rotate_clockwise,
    order=40,
)
class RotateClockwiseMenuPanel(_RotateMenuPanel):
    """Turn the layout of the selected nodes a quarter turn clockwise, in place.

    Left-to-right becomes top-to-bottom. The cards keep their own size and appearance; set the
    graph's layout direction to match.
    """

    clockwise = True
    row_label = "Rotate Clockwise"
    row_icon = hui.icon.rotate_clockwise


@panel(
    surface=SelectionLayoutMenu,
    label="Rotate Counter-clockwise",
    description="Turn the layout of the selected nodes a quarter turn counter-clockwise, in place.",
    icon=hui.icon.rotate_counter_clockwise,
    order=50,
)
class RotateCounterClockwiseMenuPanel(_RotateMenuPanel):
    """Turn the layout of the selected nodes a quarter turn counter-clockwise, in place.

    Left-to-right becomes bottom-to-top. The cards keep their own size and appearance; set the
    graph's layout direction to match.
    """

    clockwise = False
    row_label = "Rotate Counter-clockwise"
    row_icon = hui.icon.rotate_counter_clockwise
