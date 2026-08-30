"""
Stacked NodeSkin — one port column, with group support

Ports of every direction stack in a single column; this is the default skin.
"""

from typing import List
from nicegui import ui

from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types import DataPort

from haywire.core.types.enums import LayoutDirection, PortType
from haywire.ui.skin.decorator import skin
from haywire.ui.skin.visibility import NodeVisibility

from .node_skin import NodeSkin


@skin(
    label="Stacked",
    description="One port column, outlets over configs over inlets, with collapsible groups",
    _is_default=True,
)
class StackedNodeSkin(NodeSkin):
    """
    The default skin: every port type stacked in ONE column.

    Named for that column. The order within it is outlets → configs → inlets,
    and each pin is sided by the node's LayoutDirection rather than by which
    band it is in — which is what distinguishes this from
    :class:`SplitNodeSkin`, where inlets and outlets take a column each.

    Features:
    - Ports stacked in one column, each pin sided by the node's LayoutDirection
      (inlets left / outlets right under L2R, mirrored under R2L)
    - Vertical layouts (T2B / B2T) instead render inlets and outlets as bare pin
      strips on the card's top/bottom edges, leaving only configs in the body
    - Collapsible groups with visual hierarchy — horizontal layouts only
    - Header pins for ports a collapsed group hides but an edge still needs
    - Node collapse and NodeDetail honoured through ``show_of`` (ADR 0032)
    - Automatic port ordering
    """

    def render(self, main_card: ui.card, wrapper: NodeWrapper):
        """Render the complete node UI with groups."""
        node = wrapper.node
        layout: LayoutDirection = self.layout_of(wrapper)
        show: NodeVisibility = self.show_of(wrapper)

        padding = self.CARD_H_PADDING
        # Pure var() consumption — no per-node branching, ever. A graph or a
        # node overrides the look via a @theme(theme_type='node') class);
        # the browser re-resolves them without this skin being re-rendered.
        #
        # `background`, not `background-color`: a token may hold a gradient
        card_style = (
            "background: var(--hw-node-bg); "
            "border: var(--hw-node-border-width) solid var(--hw-node-border-color); "
            "border-radius: var(--hw-node-border-radius); "
            "color: var(--hw-node-text-color); "
            f"backdrop-filter: blur(10px); "
            f"overflow: visible; padding-left: {padding}px; padding-right: {padding}px;"
        )
        if show.collapsed:
            # Folded, this card is the shared header row — see NodeSkin.
            self._render_collapsed(main_card, node, wrapper, layout, card_style, show)
        elif layout.is_vertical:
            self._render_vertical(main_card, node, wrapper, layout, card_style, show)
        else:
            self._render_horizontal(main_card, node, wrapper, layout, card_style, show)

    def _render_vertical(
        self,
        main_card: ui.card,
        node,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        card_style: str,
        show: NodeVisibility,
    ):
        """Vertical layouts (T2B / B2T): inlets and outlets become bare pin
        strips on the card's top/bottom edges, leaving only configs in the body.
        """
        # `min-w-64`/`max-w-sm` size a label+widget content column that a
        # vertical card does not have — its width comes from the pin strips
        # and the config body.
        main_card.classes("w-full node-card zoom-pan-lod0").style(
            f"{card_style} {self.vertical_card_style()}"
        )

        with main_card:
            # Single diagnostics badge unifying runtime errors and advisory
            # warnings (compatibility warnings + deprecation notice). One icon,
            # one count, colored by highest severity. See _render_diagnostics_badge.
            runtime_errors = self._render_diagnostics_badge(wrapper)

            # Open with whichever strip belongs on the card's TOP edge — inlets
            # under T2B, outlets under B2T. Getting this from `top_port_type`
            # rather than hardcoding INLET is what keeps the `top: -Npx` offsets
            # pushing outward: a strip rendered at the top of the card but sided
            # "bottom" offsets DOWN, i.e. inward.
            self._render_edge_strip(node, wrapper, layout, self._top_port_type(layout), show)

            # Header with node label. Ghost pins move into the edge strips
            # instead of the header: they are inline flex items, so a
            # `top: -16px` inside a mid-card header row just shifts them 16px
            # up INSIDE the card rather than out to an edge.
            with ui.row().classes("drag-handle w-full items-center"):
                # Node title (centered/flexible)
                self._render_title(node)
                self._render_alternates_notice(wrapper, runtime_errors, show)

            # Main content: only configs stay in the body — inlets and outlets
            # became edge strips.
            with ui.row().classes("w-full gap-2"):
                with ui.column().classes("flex-1 gap-1"):
                    if node.ports:
                        self._render_port_hierarchy(
                            show.ports(node),
                            wrapper=wrapper,
                            port_type=PortType.CONFIG,
                            layout=layout,
                            show=show,
                        )

            self._render_edge_strip(node, wrapper, layout, self._bottom_port_type(layout), show)

    def _render_horizontal(
        self,
        main_card: ui.card,
        node,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        card_style: str,
        show: NodeVisibility,
    ):
        """Horizontal layouts (L2R / R2L): every port type stacks in one
        column, each pin sided by the layout, with ghost pins in the header.
        """
        main_card.classes("w-full min-w-64 max-w-sm node-card zoom-pan-lod0").style(card_style)

        with main_card:
            # Single diagnostics badge unifying runtime errors and advisory
            # warnings (compatibility warnings + deprecation notice). One icon,
            # one count, colored by highest severity. See _render_diagnostics_badge.
            runtime_errors = self._render_diagnostics_badge(wrapper)

            # Header with node label and ghost pins for hidden connected ports.
            with ui.row().classes("drag-handle w-full items-center"):
                # Root ghost pins — always-present fallback connection
                # anchors, sided by the layout direction
                self._render_root_ghost_pins(wrapper, layout)

                # Ordinary pins for inlets a collapsed GROUP hides but an edge
                # still lands on. Not ghost pins: a ghost is the root drop
                # anchor above, names no entry in node.ports, and is never
                # linked. See the glossary.
                self._render_pin_column(node.get_hidden_connected_ports(is_inlet=True), wrapper, layout)

                # Node title (centered/flexible)
                self._render_title(node)

                # Same for outlets — ordinary pins, not ghosts.
                self._render_pin_column(node.get_hidden_connected_ports(is_inlet=False), wrapper, layout)

                self._render_alternates_notice(wrapper, runtime_errors, show)

            # Main content: every port type stacks in one column, each pin
            # sided by the layout.
            with ui.row().classes("w-full gap-2"):
                with ui.column().classes("flex-1 gap-1"):
                    if node.ports:
                        visible = show.ports(node)
                        for port_type in (PortType.OUTLET, PortType.CONFIG, PortType.INLET):
                            self._render_port_hierarchy(
                                visible,
                                wrapper=wrapper,
                                port_type=port_type,
                                layout=layout,
                                show=show,
                            )

    @staticmethod
    def _top_port_type(layout: LayoutDirection) -> PortType:
        """Which port direction belongs on the card's top edge."""
        return PortType.INLET if layout.inlet_side == "top" else PortType.OUTLET

    @staticmethod
    def _bottom_port_type(layout: LayoutDirection) -> PortType:
        """Which port direction belongs on the card's bottom edge."""
        return PortType.OUTLET if layout.inlet_side == "top" else PortType.INLET

    def _render_edge_strip(
        self,
        node,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        port_type: PortType,
        show: NodeVisibility,
    ):
        """Collect a direction's visible ports and lay them along a card edge.

        Also carries the matching root ghost pin, so the always-present fallback
        anchor sits on the same card edge as the real pins it stands in for.

        Groups are skipped entirely here (settled decision): a collapsible
        hierarchy has no meaning in a flat strip, so group control ports and
        every port nested under one are left out rather than flattened in.
        """
        ports = [
            port
            for port in show.ports(node)
            if port.port_type == port_type and not port.is_group and not port.parent_group
        ]
        hidden = node.get_hidden_connected_ports(is_inlet=port_type == PortType.INLET)
        self.render_pin_strip(
            ports + list(hidden),
            wrapper,
            layout,
            ghost_for=port_type,
        )

    def _render_port_hierarchy(
        self,
        ports: List[DataPort],
        wrapper: NodeWrapper,
        port_type: PortType,
        layout: LayoutDirection | None = None,
        show: NodeVisibility | None = None,
    ):
        """
        Render ports with hierarchical group structure.

        Only renders top-level ports - child ports are rendered
        recursively inside their parent groups.

        Args:
            ports: List of visible ports (from ``show.ports(node)``)
            wrapper: NodeWrapper containing the node
            port_type: Which port direction to render
            layout: Resolved layout direction; looked up from the wrapper when omitted
            show: Resolved node visibility; looked up from the wrapper when omitted
        """
        layout = self.layout_of(wrapper) if layout is None else layout
        show = self.show_of(wrapper) if show is None else show
        for port in ports:
            # Skip ports of wrong direction
            if port.port_type != port_type:
                continue

            # Skip child ports (they're rendered inside their parent groups)
            if port.parent_group:
                continue

            # Render based on port type
            if port.is_group:
                self._render_group(port, ports, wrapper, port_type, layout, show)
            else:
                self.render_port(
                    port,
                    wrapper,
                    widget_classes="widget-container zoom-pan-lod2",
                    layout=layout,
                    show=show,
                )

    def _render_group(
        self,
        group_port: DataPort,
        all_ports: List[DataPort],
        wrapper: NodeWrapper,
        port_type: PortType,
        layout: LayoutDirection | None = None,
        show: NodeVisibility | None = None,
    ):
        """
        Render a collapsible group with visual hierarchy.

        Groups are rendered with:
        - Indentation for visual hierarchy
        - Group header with toggle widget
        - Child ports (if expanded)

        The toggle is a widget, so it follows ``show.widget`` like any other:
        below STANDARD a group renders as its (still-indented) children with no
        control, because there is nothing left on the card to toggle.

        Args:
            group_port: The group control port (boolean inlet)
            all_ports: All visible ports (to find children)
            wrapper: NodeWrapper containing the node
            port_type: Port Type
            layout: Resolved layout direction; looked up from the wrapper when omitted
            show: Resolved node visibility; looked up from the wrapper when omitted
        """
        layout = self.layout_of(wrapper) if layout is None else layout
        show = self.show_of(wrapper) if show is None else show
        node = wrapper.node
        is_expanded = node.value(group_port.id)

        # Group container with visual hierarchy
        with ui.column().classes("w-full pl-2 ml-1 gap-1"):
            # Group header with toggle
            with ui.row().classes("w-full items-center gap-1"):
                # Render group toggle widget
                if show.widget and group_port.widget_key is not None and group_port.should_show_widget():
                    self.render_widget(group_port, wrapper.node_id, classes="zoom-pan-lod2")

            # Group children (if expanded)
            if is_expanded:
                # Find and render direct children
                children = [
                    port
                    for port in all_ports
                    if port.parent_group == group_port.id and port.port_type == port_type
                ]

                for child_port in sorted(children, key=lambda p: p.order):
                    # Recursively handle nested groups
                    if child_port.is_group:
                        self._render_group(child_port, all_ports, wrapper, port_type, layout, show)
                    else:
                        self.render_port(
                            child_port,
                            wrapper,
                            widget_classes="widget-container zoom-pan-lod2",
                            layout=layout,
                            show=show,
                        )
