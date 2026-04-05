"""
Default NodeSkin with group support

This skin provides the standard node appearance with collapsible groups
"""

from typing import List
from nicegui import ui

from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types import DataPort

from haywire.core.types.enums import PortType
from haywire.ui.skin.decorator import skin

from ..skins.node_skin import NodeSkin


@skin(description="Default skin with collapsible group support", _is_default=True)
class DefaultNodeSkin(NodeSkin):
    """
    Default skin that provides the standard node appearance with group support.

    Features:
    - Two-column layout (inlets left, outlets right)
    - Collapsible groups with visual hierarchy
    - Ghost pins for collapsed groups with connections
    - Automatic port ordering
    """

    def render(self, main_card: ui.card, wrapper: NodeWrapper):
        """Render the complete node UI with groups."""
        node = wrapper.node

        padding = self.CARD_H_PADDING
        main_card.classes("w-full min-w-64 max-w-sm node-card zoom-pan-lod0").style(
            f"background-color: var(--hw-node-bg); backdrop-filter: blur(10px); "
            f"overflow: visible; padding-left: {padding}px; padding-right: {padding}px;"
        )

        with main_card:
            # Runtime errors indicator with popup
            runtime_errors = wrapper.state.get_errors()
            if runtime_errors:
                self._render_errors_button(runtime_errors)

            # Header with node label and ghost pins for hidden connected ports
            with ui.row().classes("drag-handle w-full items-center"):
                # Root ghost pins — always-present fallback connection anchors,
                # positioned at the left/right edges of the header row
                self._render_root_ghost_pins(wrapper)

                # Ghost pins for hidden inlet connections (left side)
                hidden_inlets = node.get_hidden_connected_ports(is_inlet=True)
                if hidden_inlets:
                    with ui.column().classes("gap-0 items-center"):
                        for port in hidden_inlets:
                            self._render_pin(port, wrapper, direction="left")

                # Node title (centered/flexible)
                ui.label(node.identity.label).classes("text-h6 flex-grow")

                # Ghost pins for hidden outlet connections (right side)
                hidden_outlets = node.get_hidden_connected_ports(is_inlet=False)
                if hidden_outlets:
                    with ui.column().classes("gap-0 items-center"):
                        for port in hidden_outlets:
                            self._render_pin(port, wrapper, direction="right")

                if runtime_errors:
                    if wrapper._alternate_registry_keys:
                        ui.label(
                            f"Alternate versions available: {', '.join(wrapper._alternate_registry_keys)}"
                        ).classes("text-sm hw-text-warning mb-2")

            # Main content: inlets and outlets in two columns
            with ui.row().classes("w-full gap-2"):
                # Left column: Inlets
                with ui.column().classes("flex-1 gap-1"):
                    if node.ports:
                        self._render_port_hierarchy(
                            node.get_visible_ports(),
                            wrapper=wrapper,
                            port_type=PortType.OUTLET,
                        )
                    if node.ports:
                        self._render_port_hierarchy(
                            node.get_visible_ports(),
                            wrapper=wrapper,
                            port_type=PortType.CONFIG,
                        )
                    if node.ports:
                        self._render_port_hierarchy(
                            node.get_visible_ports(),
                            wrapper=wrapper,
                            port_type=PortType.INLET,
                        )

        # Add resize handle in bottom-right corner
        if self._ui_settings.show_resize_handle:
            self._add_resize_handle(main_card, wrapper)

    def _render_port_hierarchy(self, ports: List[DataPort], wrapper: NodeWrapper, port_type: PortType):
        """
        Render ports with hierarchical group structure.

        Only renders top-level ports - child ports are rendered
        recursively inside their parent groups.

        Args:
            ports: List of visible ports (from get_visible_ports())
            wrapper: NodeWrapper containing the node
            is_inlet: True to render inlets, False for outlets
        """
        for port in ports:
            # Skip ports of wrong direction
            if port.port_type != port_type:
                continue

            # Skip child ports (they're rendered inside their parent group)
            if port.parent_group:
                continue

            # Render based on port type
            if port.is_group:
                self._render_group(port, ports, wrapper, port_type)
            else:
                self.render_port(port, wrapper, widget_classes="widget-container zoom-pan-lod2")

    def _render_group(
        self, group_port: DataPort, all_ports: List[DataPort], wrapper: NodeWrapper, port_type: PortType
    ):
        """
        Render a collapsible group with visual hierarchy.

        Groups are rendered with:
        - Border and indentation for visual hierarchy
        - Group header with toggle widget
        - Child ports (if expanded)
        - Ghost pin (if collapsed with connections)

        Args:
            group_port: The group control port (boolean inlet)
            all_ports: All visible ports (to find children)
            wrapper: NodeWrapper containing the node
            port_type: Port Type
        """
        node = wrapper.node
        is_expanded = node.value(group_port.id)

        # Group container with visual hierarchy
        with ui.column().classes("w-full pl-2 ml-1 gap-1"):
            # Group header with toggle
            with ui.row().classes("w-full items-center gap-1"):
                # Render group toggle widget
                if group_port.widget_key:
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
                        self._render_group(child_port, all_ports, wrapper, port_type)
                    else:
                        self.render_port(
                            child_port, wrapper, widget_classes="widget-container zoom-pan-lod2"
                        )
