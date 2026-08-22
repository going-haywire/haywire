"""
Error NodeSkin - Based on the DefaultNodeSkin

This skin provides error styling for nodes.
"""

from nicegui import ui

from haywire.core.node.base import BaseNode
from haywire.core.node.node_wrapper import NodeWrapper

from haywire.ui.skin.decorator import skin

from .node_skin import NodeSkin


@skin(
    description="Error skin that provides error styling for nodes",
    _is_error=True,
    hidden=True,  # Fallback skin — not offered as a choice in the skin picker
)
class ErrorNodeSkin(NodeSkin):
    """
    Error skin that provides error styling for nodes.

    This is a child class of NodeSkin with different styling
    to indicate rendering errors or fallback situations.
    """

    def render(self, main_card: ui.card, wrapper: NodeWrapper):
        node: BaseNode = wrapper.node

        # Generate unique node ID for CSS scoping
        node_id = f"error-node-{id(node)}"

        # Add CSS for error styling
        ui.add_head_html(f"""
        <style>
        .{node_id} {{
            border: 2px solid #ef4444;
            background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
            transition: all 0.2s ease;
        }}
        .{node_id} .text-h6 {{
            color: #dc2626;
        }}
        .{node_id} .widget-container {{
            opacity: 0;
            transition: opacity 0.3s ease;
            max-height: 0;
            overflow: hidden;
        }}
        .{node_id}:hover .widget-container,
        .{node_id}:focus-within .widget-container {{
            opacity: 1;
            max-height: 200px;
        }}
        .{node_id}:hover,
        .{node_id}:focus-within {{
            box-shadow: 0 4px 12px var(--hw-danger);
        }}
        </style>
        """)

        padding = self.CARD_H_PADDING
        # `node-card` is a behavioural contract, not styling: canvas.vue keys
        # the manual-resize clamp release off it. `error-node-card` is a sibling
        # token, NOT a variant — CSS class selectors match whole tokens — so
        # without `node-card` this card silently caps at max-w-sm mid-drag.
        # See docs/components/skins/skin-canon.md.
        main_card.classes(
            f"w-full min-w-64 max-w-sm node-card error-node-card {node_id} zoom-pan-lod0"
        ).style(
            f"background-color: var(--hw-warning); backdrop-filter: blur(10px); "
            f"overflow: visible; padding-left: {padding}px; padding-right: {padding}px;"
        )

        with main_card:
            # Error header
            with ui.column().classes("items-left"):
                with ui.row():
                    ui.label(node.identity.label).classes("text-h6")

                # Runtime errors indicator with popup (error skin has no
                # advisory warnings — pass an empty warnings list).
                runtime_errors = wrapper.state.get_errors()
                if runtime_errors:
                    self._render_diagnostics_button(runtime_errors, [], wrapper.node_id)

            # Main content: inlets and outlets in two columns.
            #
            # Both loops filter. Every port id must appear exactly ONCE in the
            # DOM: pins carry `id=generate_pin_uuid(node_id, port.id)` and the
            # connection layer resolves them with getElementById, so a second
            # copy does not merely look doubled — it shadows the real pin and
            # edges attach to whichever came first in document order.
            ports = list(node.ports.values())
            with ui.row().classes("w-full gap-2"):
                # Left column: Inlets
                with ui.column().classes("flex-1 gap-1"):
                    inlets = [p for p in ports if p.is_inlet()]
                    if inlets:
                        ui.label("Inputs").classes("font-bold text-sm")
                        for inlet in inlets:
                            self.render_port(inlet, wrapper)

                # Right column: Outlets
                with ui.column().classes("flex-1 gap-1"):
                    outlets = [p for p in ports if p.is_outlet()]
                    if outlets:
                        ui.label("Outputs").classes("font-bold text-sm")
                        for outlet in outlets:
                            self.render_port(outlet, wrapper)

            # Config ports carry no pin, so they belong to neither column.
            # Rendering them full width beneath keeps them visible — this is
            # the skin a user reads while diagnosing a broken node, so dropping
            # a whole port category from it would be its own bug.
            configs = [p for p in ports if p.is_config()]
            if configs:
                with ui.column().classes("w-full gap-1"):
                    for config in configs:
                        self.render_port(config, wrapper)

            # Footer with port counts
            with ui.row().classes("w-full justify-between mt-2"):
                inlet_count = len([p for p in node.ports.values() if p.is_inlet()])
                outlet_count = len([p for p in node.ports.values() if p.is_outlet()])
                ui.label(f"↓ {inlet_count}").classes("text-caption")
                ui.label(f"↑ {outlet_count}").classes("text-caption")
