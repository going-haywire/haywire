"""Skin for the annotation node — a box of text with pins on all four sides.

Each card side holds one absolutely positioned strip. Its pins (a control pin,
then the side's grown swinglets by index) are centred along the side as a group.
The side's open slot follows the last pin in a zero-length box, so it takes no
room from the group, and sits at the side's centre when the side has no pins; it
stays hidden, keeping its box, until the card is hovered or an edge drag is in
progress. A swinglet is rendered with ``_LAYOUT[side]``, the one
``LayoutDirection`` whose inlet side is that side, so its CSS side and its
direction vector come from the same source.

The node's ghost pins get a centred strip of their own on their side, drawn
before the pin strip so the real pins sit on top.

The node binds itself to this skin by registry-key string; this skin never
imports the node class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from haywire.barn.builtin.widget_keys import NOTE_TEXT_WIDGET
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.enums import LayoutDirection
from haywire.ui.skin.base import BaseSkin
from haywire.ui.skin.decorator import skin
from haywire.ui.skin.pin_render import (
    GHOST_PIN_SIZE,
    add_pin_tooltip,
    render_ghost_pin,
    render_pin,
    resolve_layout_direction,
)

if TYPE_CHECKING:
    from haywire.core.types.port import DataPort

_PIN_GUTTER = 18
_PIN_PROTRUSION = 0
# Must match the padding the card paints: render_pin offsets pins against it.
_CARD_PADDING = 12

#: The card sides, in the order the node's port ids name them.
_SIDES = ("top", "right", "bottom", "left")

#: The one layout that puts a swinglet on each side: its inlet side.
_LAYOUT: dict[str, LayoutDirection] = {
    "left": LayoutDirection.LEFT_TO_RIGHT,
    "right": LayoutDirection.RIGHT_TO_LEFT,
    "top": LayoutDirection.TOP_TO_BOTTOM,
    "bottom": LayoutDirection.BOTTOM_TO_TOP,
}

#: The cross-axis span of each side's strip.
_SPAN = {
    "top": "left: 0; right: 0;",
    "bottom": "left: 0; right: 0;",
    "left": "top: 0; bottom: 0;",
    "right": "top: 0; bottom: 0;",
}

#: The flex direction along each side, and the alignment that keeps each pin's
#: static position on the side's card edge.
_FLOW = {
    "top": "flex-direction: row; align-items: flex-start;",
    "bottom": "flex-direction: row; align-items: flex-end;",
    "left": "flex-direction: column; align-items: flex-start;",
    "right": "flex-direction: column; align-items: flex-end;",
}

#: The size property along each side.
_LENGTH = {"top": "width", "bottom": "width", "left": "height", "right": "height"}

#: Class of a pin hidden until its card is hovered or an edge drag is active.
_REVEAL = "hw-pin-reveal"


def _parse(port_id: str) -> tuple[str, int] | None:
    """The side and index a port id records (``right_2``), or ``None``."""
    side, _, index = port_id.partition("_")
    if side not in _SIDES or not index.isdigit():
        return None
    return side, int(index)


#: CSS font stacks of the node's ``font`` choices.
_FONT_STACKS = {
    "sans": "inherit",
    "serif": "Georgia, 'Times New Roman', serif",
    "mono": "ui-monospace, Menlo, Consolas, monospace",
    "handwriting": "'Segoe Print', 'Bradley Hand', 'Comic Sans MS', cursive",
}

#: Flex alignment of each horizontal and vertical alignment choice.
_JUSTIFY = {"left": "flex-start", "center": "center", "right": "flex-end"}
_VERTICAL = {"top": "flex-start", "middle": "center", "bottom": "flex-end"}


def _bag(node: object) -> Any:
    """The node's ``annotation`` settings bag."""
    return node.annotation  # type: ignore[attr-defined]


def _text_style(bag: Any) -> str:
    """CSS the note's text inherits: font, weight, style, decoration, alignment, color and highlight.

    The highlight and the text's place on the card are custom properties the text widget reads.
    """
    parts = [
        f"font-family: {_FONT_STACKS.get(bag.font, 'inherit')};",
        f"font-size: {int(bag.font_size)}px;",
        f"font-weight: {'700' if bag.bold else '400'};",
        f"font-style: {'italic' if bag.italic else 'normal'};",
        f"text-decoration: {'underline' if bag.underline else 'none'};",
        f"text-align: {bag.h_align if bag.h_align in _JUSTIFY else 'left'};",
        f"--hw-note-highlight: {bag.highlight_color or 'transparent'};",
        f"--hw-note-justify: {_VERTICAL.get(bag.v_align, 'flex-start')};",
        f"--hw-note-align: {_JUSTIFY.get(bag.h_align, 'flex-start')};",
    ]
    if bag.text_color:
        parts.append(f"color: {bag.text_color};")
    return " ".join(parts)


def _strip(side: str) -> ui.element:
    """An absolutely positioned strip along *side* that centres its items."""
    return ui.element("div").style(
        "position: absolute; display: flex; justify-content: center; "
        "overflow: visible; pointer-events: none; "
        f"{_SPAN[side]} {_FLOW[side]} {side}: {_CARD_PADDING}px;"
    )


def _slot_box(side: str, *, centred: bool) -> ui.element:
    """A zero-length box in *side*'s strip: the slot inside overflows it and takes no room.

    With ``centred`` the slot straddles the box; otherwise it hangs after it.
    """
    return ui.element("div").style(
        f"display: flex; flex: none; {_LENGTH[side]}: 0; overflow: visible; "
        f"justify-content: {'center' if centred else 'flex-start'}; {_FLOW[side]}"
    )


@skin(description="Annotation skin — a box of text with pins on every side.", hidden=True)
class AnnotationSkin(BaseSkin):
    """Draws an annotation node: its text, and pins centred along each card edge.

    Hover a card to show the open pin on each side; connect to one to grow a
    pin there. Double-click the text to edit it.
    """

    def render(self, main_card: ui.card, wrapper: NodeWrapper, *, on_stage: bool):
        node = wrapper.node
        bag = _bag(node)

        # `background`, not `background-color`: --hw-node-bg may hold a gradient.
        main_card.classes("node-card drag-handle zoom-pan-lod0").style(
            "background: var(--hw-node-bg); "
            "border: var(--hw-node-border-width) solid var(--hw-node-border-color); "
            "border-radius: var(--hw-node-border-radius); color: var(--hw-node-text-color); "
            f"position: relative; overflow: visible; padding: {_CARD_PADDING}px; "
            "min-width: 160px; min-height: 80px;"
        )
        with main_card:
            # The text widget fills this box and inherits the note's look from it.
            with ui.element("div").style(
                "flex: 1 1 auto; width: 100%; display: flex; flex-direction: column; " + _text_style(bag)
            ):
                self.render_setting_widget(bag, "text", wrapper.node_id, widget_key=NOTE_TEXT_WIDGET)

        pins = self._pins_by_side(wrapper, on_stage=on_stage)
        for side in _SIDES:
            with main_card:
                self._render_ghosts(wrapper, side)
                # A slot on a side without pins takes the side's centre.
                centred = all(reveal for _, _, reveal in pins[side])
                with _strip(side):
                    for port, layout, reveal in pins[side]:
                        if reveal:
                            with _slot_box(side, centred=centred):
                                self._render_pin(port, wrapper.node_id, layout, reveal, on_stage=on_stage)
                        else:
                            self._render_pin(port, wrapper.node_id, layout, reveal, on_stage=on_stage)

    def _pins_by_side(
        self, wrapper: NodeWrapper, *, on_stage: bool
    ) -> dict[str, list[tuple[DataPort, LayoutDirection, bool]]]:
        """Each side's pins in drawing order: control pin, grown pins by index, then the slot.

        With ``on_stage`` a port that is not an on-stage port is left out.

        Each entry is the port, the layout it renders with, and whether it is a
        slot, shown only on hover.
        """
        from haywire.barn.builtin.types import ADD

        node = wrapper.node
        node_layout = resolve_layout_direction(wrapper)
        by_side: dict[str, list[tuple[DataPort, LayoutDirection, bool]]] = {side: [] for side in _SIDES}

        for port_id in ("exec", "done"):
            port = node.ports.get(port_id)
            if port is None or not (_bag(node).show_control_pins or port.is_linked()):
                continue
            if on_stage and not port.on_stage:
                continue
            by_side[node_layout.side_for(port)].append((port, node_layout, False))

        grown: list[tuple[int, str, DataPort]] = []
        slots: list[tuple[int, str, DataPort]] = []
        for port in node.ports.values():
            parsed = _parse(port.id)
            if parsed is None or not port.has_pin() or (on_stage and not port.on_stage):
                continue
            side, index = parsed
            is_slot = port.type_cls is not None and issubclass(port.type_cls, ADD)
            (slots if is_slot else grown).append((index, side, port))

        for _, side, port in sorted(grown, key=lambda g: g[0]):
            by_side[side].append((port, _LAYOUT[side], False))
        for _, side, port in sorted(slots, key=lambda s: s[0]):
            by_side[side].append((port, _LAYOUT[side], True))
        return by_side

    def _render_pin(
        self, port: DataPort, node_id: str, layout: LayoutDirection, reveal: bool, *, on_stage: bool
    ) -> None:
        pin_el = render_pin(
            port,
            node_id,
            layout=layout,
            # A pin clips its overflow, so a flex item would shrink to nothing in the slot's box.
            cell_style="flex-shrink: 0;",
            pin_gutter=_PIN_GUTTER,
            card_padding=_CARD_PADDING,
            pin_protrusion=_PIN_PROTRUSION,
            pin_icons=self.pin_icons,
            on_stage=on_stage,
        )
        if pin_el is None:
            return
        add_pin_tooltip(pin_el, port)
        if reveal:
            pin_el.classes(_REVEAL)

    def _render_ghosts(self, wrapper: NodeWrapper, side: str) -> None:
        """Render, in a strip of their own, the ghost pins whose side in the node's layout is *side*."""
        layout = resolve_layout_direction(wrapper)
        ghosts = [
            is_inlet
            for is_inlet in (True, False)
            if (layout.inlet_side if is_inlet else layout.outlet_side) == side
        ]
        if not ghosts:
            return
        # Its own stacking context keeps a ghost under the pins it overlaps: a hovered
        # pin drops to the canvas's node-hover z-index, below an unhovered ghost.
        with _strip(side).style("z-index: 0;"):
            for is_inlet in ghosts:
                ghost = render_ghost_pin(
                    wrapper.node_id,
                    layout=layout,
                    is_inlet=is_inlet,
                    offset=_CARD_PADDING + GHOST_PIN_SIZE // 2 + _PIN_PROTRUSION,
                )
                ghost.classes(_REVEAL)
