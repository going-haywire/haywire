"""A progress bar that shows a PROGRESS value."""

from __future__ import annotations

from typing import Any

from nicegui import ui

from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

#: The sweep animates the fill's background, so the bar never becomes its own compositing layer.
_PROGRESS_CSS = """
.hw-progress-track { height: 3px; border-radius: 2px; background: var(--hw-border); overflow: hidden; }
.hw-progress-fill { height: 100%; width: 0; background: var(--hw-accent); }
.hw-progress-sweep {
    width: 100%;
    background: linear-gradient(90deg, transparent 0%, var(--hw-accent) 50%, transparent 100%);
    background-size: 50% 100%;
    background-repeat: no-repeat;
    animation: hw-progress-sweep 1.2s linear infinite;
}
@keyframes hw-progress-sweep { from { background-position: -100% 0; } to { background-position: 200% 0; } }
"""


def _ensure_progress_css() -> None:
    """Add the progress stylesheet to the current page once."""
    client = ui.context.client
    if not getattr(client, "_hw_progress_css", False):
        ui.add_css(_PROGRESS_CSS)
        client._hw_progress_css = True  # type: ignore[attr-defined]


@widget(description="Progress bar")
class ProgressWidget(BaseWidget):
    """Shows how far a node is with its work.

    The bar is empty while the node is idle, sweeps while the node is busy with
    no known end, and fills while it reports a fraction. The text above the bar
    names what the node is doing. The widget only displays; it has no input.
    """

    def build(self) -> Any:
        _ensure_progress_css()
        with ui.column().classes("w-full gap-0").props("data-hw-progress") as root:
            # A non-breaking space keeps the text line's height while idle, so the card never resizes.
            self._label = (
                ui.label(" ")
                .classes("text-xs truncate w-full")
                .style("color: var(--hw-text-muted); line-height: 1rem;")
            )
            with ui.element("div").classes("hw-progress-track w-full"):
                self._fill = ui.element("div").classes("hw-progress-fill")
        return root

    def on_model_changed(self, value: Any) -> None:
        """Show *value*: an empty bar when idle, a sweep without a fraction, a fill with one."""
        active = bool(getattr(value, "active", False))
        fraction = getattr(value, "fraction", None)
        label = getattr(value, "label", "") if active else ""
        self._label.set_text(label or " ")
        if not active:
            state, width = "idle", "0%"
        elif fraction is None:
            state, width = "busy", "100%"
        else:
            state, width = "busy", f"{fraction * 100:.1f}%"
        self._fill.classes(
            add="hw-progress-sweep" if active and fraction is None else None,
            remove=None if active and fraction is None else "hw-progress-sweep",
        )
        self._fill.style(replace=f"width: {width};")
        if self.ui_element is not None:
            self.ui_element.props(f'data-hw-progress="{state}"')
