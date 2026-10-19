"""The widget-node skin: a widget node on a stage, drawn as its control with the node label on its left."""

from __future__ import annotations

from typing import Any

from nicegui import ui

from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.skin.fonts import FONT_STACKS
from haywire.core.skin.tags import SKIN_TAG_SPECIAL, SKIN_TAG_STAGE_ONLY, SKIN_TAG_WIDGET_NODE
from haywire.core.types.enums import LayoutDirection, PortOrigin
from haywire.core.types.port import DataPort
from haywire.ui.skin.base import BaseSkin
from haywire.ui.skin.decorator import skin
from haywire.ui.skin.pin_render import render_pin

_PIN_GUTTER = 18
_PIN_PROTRUSION = 0
# render_pin offsets pins against the padding the card paints, so the two must match.
_CARD_PADDING = 4
_LAYOUT = LayoutDirection.LEFT_TO_RIGHT


@skin(
    label="Widget Node",
    description="The control alone, with the node label on its left — for widget nodes on a stage",
    tags=[SKIN_TAG_SPECIAL, SKIN_TAG_STAGE_ONLY, SKIN_TAG_WIDGET_NODE],
)
class WidgetNodeSkin(BaseSkin):
    """Draws a widget node as its control, with the node label on the left and no frame.

    It draws the widget of each outlet the node itself declares, never that of a
    setting promoted to a port. Rename the node to change the caption.

    The node's *style* settings set the label's font, size, weight, colour and
    alignment, the card's background and border, and where the label sits: left of
    the control (half the row, up to *Max Label Width*), above it, or nowhere.

    Widget nodes use it on the stage, where they draw no pins. A skin tagged
    `special`, `stage-only` and `widget-node` is offered in the same list.
    """

    def render(self, main_card: ui.card, wrapper: NodeWrapper, *, on_stage: bool):
        node = wrapper.node
        style = getattr(node, "style", None)
        position = _get(style, "label_position", "left")
        # `drag-handle` keeps the node draggable by its label; `overflow: visible`
        # lets patch pins straddle the edges. A flex column centred on its main axis:
        # a card the user sizes taller keeps its face in the middle (the slot
        # stretches the card, see canvas.vue). compact-fields: the settings panel's
        # tight Quasar fields (app/shell.py).
        main_card.classes("node-card drag-handle zoom-pan-lod0 compact-fields").style(
            f"background: {_get(style, 'background', '') or 'transparent'}; box-shadow: none; "
            f"position: relative; overflow: visible; padding: {_CARD_PADDING}px; min-width: 180px; "
            "display: flex; flex-direction: column; justify-content: center;" + _border(style)
        )
        with main_card:
            face: ui.element
            if position == "above":
                face = ui.column().classes("w-full gap-1 no-wrap")
            else:
                face = ui.row().classes("w-full items-center gap-0 no-wrap")
            face.props(f'data-widget-node-face="{position}"')
            max_width = _get(style, "max_label_width", None)
            if position == "left" and max_width:
                # The shared split rule (app/shell.py) reads it: half the row, up to this width.
                face.style(f"--hw-max-label-width: {int(max_width)}px;")
            with face:
                if position != "hidden":
                    split = "sf-label pr-2" if position == "left" else "w-full"
                    ui.label(node.display_label).classes(f"{split} truncate").style(
                        _label_style(style)
                    ).props("data-widget-node-label")
                control = "sf-widget" if position == "left" else "w-full"
                for port in _controls(node.ports.values()):
                    # widget-container: the canvas leaves a press inside it to the widget.
                    self.render_widget(port, wrapper.node_id, classes=f"{control} widget-container min-w-0")
        if not on_stage:
            self._render_pins(main_card, wrapper)

    def honours_detail(self, *, on_stage: bool) -> bool:
        return False

    def _render_pins(self, main_card: ui.card, wrapper: NodeWrapper) -> None:
        """Draw every pin on the card edge its side names, as ``RerouteSkin`` does."""
        sides: dict[str, list[DataPort]] = {}
        for port in wrapper.node.ports.values():
            if port.has_pin():
                sides.setdefault(_LAYOUT.side_for(port), []).append(port)
        for edge, ports in sides.items():
            with main_card:
                with ui.element("div").style(
                    "position: absolute; display: flex; flex-direction: column; overflow: visible; "
                    f"top: 0; bottom: 0; justify-content: center; {edge}: {_CARD_PADDING}px;"
                ):
                    for port in ports:
                        render_pin(
                            port,
                            wrapper.node_id,
                            layout=_LAYOUT,
                            pin_gutter=_PIN_GUTTER,
                            card_padding=_CARD_PADDING,
                            pin_protrusion=_PIN_PROTRUSION,
                            pin_icons=self.pin_icons,
                            on_stage=False,
                        )


def _get(style: Any, name: str, default: Any) -> Any:
    """Return field *name* of the node's style bag, or *default* for a node without one."""
    return default if style is None else getattr(style, name, default)


def _label_style(style: Any) -> str:
    """CSS for the label: font, size, weight, slant, alignment and colour."""
    parts = [
        f"font-family: {FONT_STACKS.get(_get(style, 'font', 'sans'), 'inherit')};",
        f"font-size: {int(_get(style, 'font_size', 14))}px;",
        f"font-weight: {'700' if _get(style, 'bold', False) else '400'};",
        f"font-style: {'italic' if _get(style, 'italic', False) else 'normal'};",
        f"text-align: {_get(style, 'label_align', 'left')};",
    ]
    color = _get(style, "label_color", "")
    if color:
        parts.append(f"color: {color};")
    return " ".join(parts)


def _border(style: Any) -> str:
    """CSS for the card's border: the theme's node border, or none."""
    if not _get(style, "border", False):
        return ""
    return (
        " border: var(--hw-node-border-width) solid var(--hw-node-border-color);"
        " border-radius: var(--hw-node-border-radius);"
    )


def _controls(ports) -> list[DataPort]:
    """Return the outlets the node declares that carry a widget."""
    return [p for p in ports if p.is_outlet() and p.origin is PortOrigin.DECLARED and p.widget_key]
