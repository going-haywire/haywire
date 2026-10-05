"""ArrowHeadWidget — picks an arrow head from the shared head vocabulary."""

from __future__ import annotations

from typing import Any

from nicegui import ui

from haywire.core.edge.arrow_heads import ARROW_HEADS, NO_HEAD, ArrowHead, get_arrow_head
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget


def preview_svg(head: ArrowHead | None) -> str:
    """Return an inline SVG of *head* at the end of a short line, drawn in ``currentColor``.

    ``None`` draws the line alone. The glyph is the head's own markup with
    ``context-stroke`` swapped for ``currentColor``, since ``context-stroke``
    paints only inside a marker.
    """
    inset = head.inset if head is not None else 6.0
    glyph = head.svg.replace("context-stroke", "currentColor") if head is not None else ""
    line_end = 0 if head is not None else inset
    return (
        f'<svg width="44" height="16" viewBox="-8 -4 {8 + inset + 1} 8" style="overflow: visible">'
        f'<path d="M-8,0 L{line_end},0" stroke="currentColor" stroke-width="1" fill="none"/>'
        f"{glyph}</svg>"
    )


@widget(description="Arrow head picker")
class ArrowHeadWidget(BaseWidget):
    """Picks the arrow head an edge draws at one end.

    The button shows the current head. Its menu lists *None* and the four
    common arrows; *More* reveals every head. The value is the head's name,
    or `none` for no head.
    """

    def build(self) -> Any:
        button = ui.button().props("flat dense no-caps").classes("w-full")
        with button:
            self._preview = ui.html("")
            with ui.menu() as self._menu:
                with ui.grid(columns=5).classes("p-1 gap-0"):
                    self._item(None)
                    for head in ARROW_HEADS:
                        if head.common:
                            self._item(head)
                self._more = (
                    ui.button("More", on_click=self._show_all)
                    .props("flat dense no-caps")
                    .classes("w-full")
                    .mark("arrow-head-more")
                )
                with ui.grid(columns=5).classes("p-1 gap-0") as self._all:
                    for head in ARROW_HEADS:
                        if not head.common:
                            self._item(head)
                self._all.set_visibility(False)
        return button

    def _item(self, head: ArrowHead | None) -> None:
        name = head.name if head is not None else NO_HEAD
        label = head.label if head is not None else "None"
        with (
            ui.button(on_click=lambda _, n=name: self._pick(n))
            .props("flat dense")
            .tooltip(label)
            .mark(f"arrow-head-{name}")
        ):
            ui.html(preview_svg(head))

    def _show_all(self) -> None:
        self._all.set_visibility(True)
        self._more.set_visibility(False)

    def _pick(self, name: str) -> None:
        self._menu.close()
        self.set_value(name)

    def on_model_changed(self, value: Any) -> None:
        """Show the stored head on the button."""
        self._preview.set_content(preview_svg(get_arrow_head(value)))
