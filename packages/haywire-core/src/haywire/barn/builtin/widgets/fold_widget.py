"""The header of a fold: a disclosure triangle, the fold's label and its open state."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.skin.pin_render import add_pin_tooltip
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget


@widget(description="Fold header")
class FoldWidget(BaseWidget):
    """Opens and closes a fold of ports on a node card.

    Click the header to open or close the fold. The triangle points down while
    the fold is open, and the checkbox at the end shows the same state as the
    fold's value, which a node can read like any other port. Hover the triangle
    for the fold's description.

    Config options (via `FoldWidget.config(properties={...})`):

    - `text` (str): The fold's label.
    - `description` (str): The text under the label in the triangle's tooltip.
    """

    def build(self) -> Any:
        properties = self._config.get("properties", {})
        text = properties.get("text", "")
        with (
            ui.row()
            .classes("w-full items-center gap-1 cursor-pointer")
            .props(f'data-hw-fold-id="{self.port_id}"')
            .on("click", self._toggle) as root
        ):
            self._triangle = ui.icon(hui.icon.fold_open).classes("text-sm")
            ui.label(text).classes("text-xs grow")
            self._check = ui.icon(hui.icon.checked).classes("text-sm")
        # Triggered by the triangle: a tooltip trigger must be small (see add_pin_tooltip).
        add_pin_tooltip(
            root,
            SimpleNamespace(label=text, description=properties.get("description", "")),  # type: ignore[arg-type]
            trigger_el=self._triangle,
        )
        return root

    def _toggle(self, _event: Any = None) -> None:
        self.set_value(not bool(self.get_value()))

    def on_model_changed(self, value: Any) -> None:
        """Show *value* as the fold's open state."""
        is_open = bool(value)
        self._triangle.set_name(hui.icon.fold_open if is_open else hui.icon.fold_closed)
        self._check.set_name(hui.icon.checked if is_open else hui.icon.unchecked)
        if self.ui_element is not None:
            self.ui_element.props(f'data-hw-fold-open="{str(is_open).lower()}"')
