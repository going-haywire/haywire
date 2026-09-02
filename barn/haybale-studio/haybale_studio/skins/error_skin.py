"""
Error NodeSkin - the fallback card for a node that could not be rendered

Structurally a two-band split (see SplitNodeSkin) with error styling, and one
deliberate difference: it always shows everything.
"""

from nicegui import ui

from haywire.core.node.base import BaseNode
from haywire.core.node.node_wrapper import NodeWrapper

from haywire.ui.skin.decorator import skin

from .node_skin import NodeSkin


@skin(
    label="Error",
    description="Error skin that provides error styling for nodes",
    _is_error=True,
    hidden=True,  # Fallback skin — not offered as a choice in the skin picker
)
class ErrorNodeSkin(NodeSkin):
    """
    Error skin that provides error styling for nodes.

    This is the card a user stares at while diagnosing a broken node — either
    one whose own skin raised, or one pinned to a skin that no longer resolves.
    It lays ports out the way :class:`SplitNodeSkin` does (inlets and outlets in
    columns, pinless configs full width beneath) so the shape is familiar, but
    it renders through its own body rather than subclassing: a fallback that
    inherits another skin's render path can be taken down by that skin's bugs,
    which is the one thing this card must not do.

    It ALWAYS shows everything: ``render()`` never checks Node collapse at
    all, and reads ``node.get_visible_ports()`` unconditionally rather than
    the folded-card filter. Node collapse is a performance trade — draw fewer
    ports on cards you are not reading. This is the card you ARE reading, and
    the node behind it is already broken: hiding its ports to save elements
    would withhold exactly the information the user opened it for. A node
    folded to a title is a particularly bad failure mode here, since the fold
    would hide the fact that anything is wrong.
    """

    def card_classes(self, wrapper: NodeWrapper) -> str:
        """`error-node-card` is a sibling token, NOT a substitute for
        `node-card` — CSS class selectors match whole tokens, so a card
        carrying only this one silently caps at max-w-sm mid-drag. The shared
        `node-card` comes from whoever builds the card; this only adds to it.
        """
        return "error-node-card"

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
        .{node_id}:hover,
        .{node_id}:focus-within {{
            box-shadow: 0 4px 12px var(--hw-danger);
        }}
        </style>
        """)

        padding = self.CARD_H_PADDING
        main_card.classes(
            f"w-full min-w-64 max-w-sm node-card zoom-pan-lod0 {self.card_classes(wrapper)} {node_id}"
        ).style(
            # No backdrop-filter, and no --hw-node-backdrop-blur either: this
            # card hardcodes an opaque --hw-warning rather than reading
            # --hw-node-bg, so a backdrop blur is composited underneath it and
            # is unobservable in either shipped theme. Consuming the token here
            # would be a var that is set, accepted, and does nothing.
            f"background-color: var(--hw-warning); "
            f"overflow: visible; padding-left: {padding}px; padding-right: {padding}px;"
        )

        layout = self.layout_of(wrapper)

        with main_card:
            # Header. The badge call is the shared one, so this card cannot pick
            # up the comment marker and forget the diagnostics one (or vice
            # versa) the way its hand-rolled predecessor could.
            with ui.row().classes("drag-handle w-full items-center"):
                self._render_root_ghost_pins(wrapper, layout)
                self._render_title(node)
            runtime_errors = self._render_diagnostics_badge(wrapper)
            self._render_alternates_notice(wrapper, runtime_errors)

            # Main content: inlets and outlets in two columns.
            #
            # Both loops filter. Every port id must appear exactly ONCE in the
            # DOM: pins carry `id=generate_pin_uuid(node_id, port.id)` and the
            # connection layer resolves them with getElementById, so a second
            # copy does not merely look doubled — it shadows the real pin and
            # edges attach to whichever came first in document order.
            #
            # `get_visible_ports()` rather than `node.ports.values()`: it also
            # drops sections and group control ports, neither of which is a
            # renderable port. This skin never folds, so it is always the
            # full visible list, never the collapsed filter.
            ports = node.get_visible_ports()
            inlets = [p for p in ports if p.is_inlet()]
            outlets = [p for p in ports if p.is_outlet()]

            # Columns follow the flow direction, as in the split skin: the
            # inlet column is whichever side inlets' pins protrude from, so a
            # pin and its own label stay on the same side of the card.
            columns = (("Inputs", inlets), ("Outputs", outlets))
            if layout.inlet_side == "right":
                columns = columns[::-1]
            with ui.row().classes("w-full gap-2"):
                for heading, group in columns:
                    with ui.column().classes("flex-1 gap-1 min-w-0"):
                        if group:
                            ui.label(heading).classes("font-bold text-sm")
                            for port in group:
                                self.render_port(port, wrapper, layout=layout)

            # Config ports carry no pin, so they belong to neither column.
            # Rendering them full width beneath keeps them visible — this is
            # the skin a user reads while diagnosing a broken node, so dropping
            # a whole port category from it would be its own bug.
            configs = [p for p in ports if p.is_config()]
            if configs:
                with ui.column().classes("w-full gap-1"):
                    for config in configs:
                        self.render_port(config, wrapper, layout=layout)

            # Footer with port counts
            with ui.row().classes("w-full justify-between mt-2"):
                ui.label(f"↓ {len(inlets)}").classes("text-caption")
                ui.label(f"↑ {len(outlets)}").classes("text-caption")
