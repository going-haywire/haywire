from nicegui import ui
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.node.base import BaseNode

from haywire.ui.skin.decorator import skin

from haybale_studio.skins.node_skin import NodeSkin


@skin(description="Custom skin for nodes with special styling")
class ExampleNodeSkin(NodeSkin):
    """Custom skin for nodes with special styling.

    Two-band layout rather than the default skin's single stack: config ports
    span the full card width on top, then inlets and outlets sit side by side
    beneath. Ports are rendered through ``render_port``, which places each pin
    on the card edge its direction implies — so the left column's pins straddle
    the card's left border and the right column's its right.

    Configs get the full width precisely *because* they carry no pin: with no
    edge to attach to, nothing anchors them to a side, and their widgets are
    the ones that actually need room. Squeezing them into a third column made
    every config widget unusably narrow.
    """

    def render(self, main_card: ui.card, wrapper: NodeWrapper):
        node: BaseNode = wrapper.node
        node_id = f"example-node-{id(node)}"

        # Custom math-themed CSS.
        #
        # Deliberately NOT styled here: `.widget-container`. Inline-widget
        # reveal belongs to the framework, not to a skin — canvas.vue declares
        # `[data-node-id] .widget-container { opacity: 0 !important;
        # max-height: 0 !important; transition: ... !important }` and reveals
        # on `.node-selected`. A skin's own opacity/max-height/transition rules
        # on that class are silently outranked, and `!important` on the
        # transition shorthand means even non-conflicting properties stop
        # animating. This skin used to carry a `:hover` reveal here that never
        # once fired.
        ui.add_head_html(f"""
        <style>
        .{node_id} {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 16px;
            border: 3px solid #4f46e5;
        }}
        .{node_id} .text-h6 {{
            color: #fbbf24;
            font-weight: bold;
        }}
        </style>
        """)

        # `node-card` is load-bearing, not cosmetic: canvas.vue keys the
        # manual-resize clamp release off it (`.ui-node-slot[data-size-adapt=
        # "manual*"] .node-card { max-width: none }`), and pan.vue restores
        # pointer-events/user-select through it. Without the class the card
        # stops growing at `max-w-sm` while the slot keeps expanding.
        # `math-node-card` is a sibling class, NOT a substitute.
        layout = self.layout_of(wrapper)
        if layout.is_vertical:
            # `min-w-64`/`max-w-sm` size a label+widget content column that a
            # vertical card does not have.
            main_card.classes(f"w-full node-card zoom-pan-lod0 math-node-card {node_id}").style(
                self.vertical_card_style()
            )
        else:
            main_card.classes(f"w-full min-w-64 max-w-sm node-card zoom-pan-lod0 math-node-card {node_id}")

        with main_card:
            ports = node.get_visible_ports()
            configs = [port for port in ports if port.is_config()]
            inlets = [port for port in ports if port.is_inlet()]
            outlets = [port for port in ports if port.is_outlet()]

            # Vertical: whichever direction belongs on the card's TOP edge goes
            # first — inlets under T2B, outlets under B2T. Rendering a strip at
            # the top of the card while its pins are sided "bottom" would offset
            # them DOWN, i.e. inward.
            top_first = layout.inlet_side == "top"
            if layout.is_vertical:
                self.render_pin_strip(inlets if top_first else outlets, wrapper, layout)

            # Math-themed header
            with ui.row().classes("w-full items-center gap-2"):
                ui.icon("calculate", color="yellow").classes("text-lg")
                ui.label("Math Node").classes("text-h6 flex-1")

            # Configs first, spanning the whole card. `_render_config` already
            # lays each row out at `width: 100%`, so the band takes whatever
            # width the card has. Unchanged by direction — pinless ports have
            # no edge to move to.
            if configs:
                with ui.column().classes("w-full gap-1"):
                    ui.label("Config").classes("font-bold text-sm")
                    for port in configs:
                        self.render_port(port, wrapper, layout=layout)

            if layout.is_vertical:
                self.render_pin_strip(outlets if top_first else inlets, wrapper, layout)
            else:
                # Inlets and outlets side by side beneath. An empty column is
                # omitted rather than rendered blank, so an outlet-only node
                # keeps its pins on the card's outer edge. `min-w-0` lets each
                # flex column shrink below its content width — without it the
                # columns fight over the card and the pins drift off the border.
                #
                # Column ORDER stays inlets-first under R2L; only the pins flip
                # sides. Mirroring the columns too is a separate decision.
                columns = (("Inputs", inlets), ("Outputs", outlets))
                if inlets or outlets:
                    with ui.row().classes("w-full gap-2"):
                        for heading, group in columns:
                            if not group:
                                continue
                            with ui.column().classes("flex-1 gap-1 min-w-0"):
                                ui.label(heading).classes("font-bold text-sm")
                                for port in group:
                                    self.render_port(port, wrapper, layout=layout)
