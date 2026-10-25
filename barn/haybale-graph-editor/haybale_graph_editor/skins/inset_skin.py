"""
Inset NodeSkin — a Graph-node card whose body shows its interior's stage
"""

from typing import List

from nicegui import ui

from haywire.core.di.config import get_library_system
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.skin.tags import SKIN_TAG_GRAPH_NODE, SKIN_TAG_SPECIAL
from haywire.core.types import DataPort
from haywire.core.types.enums import LayoutDirection, PortType
from haywire.ui.skin.decorator import skin

from haybale_graph_editor.editors.graph_canvas.inset_view import InsetView
from haybale_graph_editor.skins.node_skin import NodeSkin

#: The body's smallest size, in px; a manual card size adds room, never less.
INSET_FLOOR_PX: tuple[int, int] = (240, 160)

#: What the body says when the interior has nothing on stage.
PLACEHOLDER = "Nothing on stage — Enter to arrange"

#: What the body says for a node whose interior cannot be resolved.
NO_INTERIOR = "Inset cannot draw this node: it has no interior"

#: What the body says for a stand-in, a node whose class failed to build.
FAILED_TO_BUILD = "Inset cannot draw this node: it failed to build — see its errors"


@skin(
    label="Inset",
    description="The interior's stage, operable in the card",
    tags=[SKIN_TAG_SPECIAL, SKIN_TAG_GRAPH_NODE],
)
class InsetSkin(NodeSkin):
    """A Group or macro placement drawn as its interior's stage.

    The card's body shows every node the interior puts on its stage, each with
    its own stage skin at its stage position. Their widgets can be operated
    from here; the layout is arranged by entering the Group.

    In the patch the card has its title, then the body, with the card's pins on
    its edges. On a stage it is the body alone. Collapsed, it is the usual
    folded card. The body is at least 240 × 160 px and clips what lies beyond
    its edge; make the card larger to show more.
    """

    def card_classes(self, wrapper: NodeWrapper) -> str:
        """The Inset card's own token, beside the shared ``node-card``."""
        return "inset-node-card"

    def honours_detail(self, *, on_stage: bool) -> bool:
        """Never: the Inset draws no port rows for Detail to thin."""
        return False

    def render(self, main_card: ui.card, wrapper: NodeWrapper, *, on_stage: bool):
        node = wrapper.node
        layout = self.layout_of(wrapper, on_stage=on_stage)
        pins = [port for port in node.get_all_ports() if not port.is_fold and port.has_pin()]
        inlets = [port for port in pins if port.is_inlet()]
        outlets = [port for port in pins if port.is_outlet() and not port.is_swinglet()]

        if on_stage:
            main_card.classes(f"node-card zoom-pan-lod0 {self.card_classes(wrapper)}").style(
                self.card_style()
            )
            with main_card:
                self._render_body(wrapper)
        elif self.is_collapsed(wrapper):
            self._render_collapsed(main_card, node, wrapper, layout, self.card_style())
        elif layout.is_vertical:
            self._render_vertical(main_card, wrapper, layout, inlets, outlets)
        else:
            self._render_horizontal(main_card, wrapper, layout, inlets, outlets)

    def _render_horizontal(
        self,
        main_card: ui.card,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        inlets: List[DataPort],
        outlets: List[DataPort],
    ) -> None:
        """L2R / R2L: the title row, then a row holding a pin column, the body and a pin column."""
        main_card.classes(f"w-full node-card zoom-pan-lod0 {self.card_classes(wrapper)}").style(
            self.card_style()
        )
        with main_card:
            self._render_diagnostics_badge(wrapper)
            with self.header_row("gap-2"):
                self._render_root_ghost_pins(wrapper, layout)
                self._render_title(wrapper.node)
            tallest = max(len(inlets), len(outlets))
            # Positioned, so the pin columns seat on this row's edges, which are the card's.
            with (
                ui.row()
                .classes("w-full no-wrap")
                .style(f"position: relative; flex: 1 1 auto; min-height: {tallest * self.PIN_GUTTER}px;")
            ):
                self._render_pin_column(inlets, wrapper, layout, on_stage=False)
                self._render_body(wrapper)
                self._render_pin_column(outlets, wrapper, layout, on_stage=False)

    def _render_vertical(
        self,
        main_card: ui.card,
        wrapper: NodeWrapper,
        layout: LayoutDirection,
        inlets: List[DataPort],
        outlets: List[DataPort],
    ) -> None:
        """T2B / B2T: a pin strip, the title, the body, then the other pin strip."""
        widest = max(len(inlets), len(outlets)) + 1
        main_card.classes(f"w-full node-card zoom-pan-lod0 {self.card_classes(wrapper)}").style(
            f"{self.card_style()} {self.vertical_card_style()} min-width: {self.strip_min_width(widest)}px;"
        )
        top_first = layout.inlet_side == "top"
        with main_card:
            self._render_diagnostics_badge(wrapper)
            self.render_pin_strip(
                inlets if top_first else outlets,
                wrapper,
                layout,
                ghost_for=PortType.INLET if top_first else PortType.OUTLET,
                on_stage=False,
            )
            with self.header_row():
                self._render_title(wrapper.node)
            self._render_body(wrapper)
            self.render_pin_strip(
                outlets if top_first else inlets,
                wrapper,
                layout,
                ghost_for=PortType.OUTLET if top_first else PortType.INLET,
                on_stage=False,
            )

    def _render_body(self, wrapper: NodeWrapper) -> None:
        """The interior's stage, clipped to the body; the placeholder when nothing is on it."""
        width, height = INSET_FLOOR_PX
        body = (
            ui.element("div")
            .classes("hw-inset-body")
            .props("data-hw-inset")
            # align-self: NiceGUI's cards and rows align items to flex-start, so without
            # it the body never fills the card across (stage: width, patch row: height).
            .style(
                "position: relative; overflow: hidden; flex: 1 1 auto; align-self: stretch; "
                f"min-width: {width}px; min-height: {height}px;"
            )
        )
        definition = getattr(wrapper.node, "resolve_definition", lambda: None)()
        if definition is None:
            # Offered for Graph-nodes only, so this is a node that broke; say so rather than draw.
            with body:
                ui.label(FAILED_TO_BUILD if wrapper.is_stand_in else NO_INTERIOR).classes(
                    "absolute inset-0 flex items-center justify-center text-center p-2 "
                    "text-xs hw-text-danger"
                )
            return
        view = InsetView(
            body,
            definition,
            get_library_system().get_skin_factory(),
            self._nodeids_routes.get(wrapper.node_id),
        )
        self.on_card_cleanup(wrapper.node_id, view.cleanup)
        if not view.cards:
            with body:
                ui.label(PLACEHOLDER).classes(
                    "absolute inset-0 flex items-center justify-center text-xs hw-text-muted"
                )
