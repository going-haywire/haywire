"""An editor for a square matrix: one number per cell, row by row."""

from __future__ import annotations

from typing import Any

from nicegui import ui

from haywire.ui.components.number.drag import NumberDrag
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

# The step arrows take 40 px of a cell that a 4x4 matrix in a narrow card can spare none of.
_MATRIX_CSS = ".hw-matrix .number-drag__arrow { display: none; }"


@widget(description="Matrix editor widget, one number per cell")
class MatrixWidget(BaseWidget):
    """Edits a square matrix, one number per cell, with rows running across."""

    def build(self) -> Any:
        self._size = int(self._config.get("properties", {}).get("size", 3))
        current = self._rows()
        ui.add_css(_MATRIX_CSS)
        self._cells: list[list[NumberDrag]] = []
        with ui.grid(columns=self._size).classes("hw-matrix w-full gap-1") as root:
            for row in range(self._size):
                cells = []
                for col in range(self._size):
                    cell = NumberDrag(
                        value=current[row][col],
                        on_change=lambda e, r=row, c=col: self._on_cell(r, c, e),
                    ).classes("w-full min-w-0")
                    cell.props(f'data-matrix-cell="{row},{col}"')
                    cells.append(cell)
                self._cells.append(cells)
        return root

    def _rows(self) -> list[list[Any]]:
        """Return a copy of the current rows, so an edit never reaches a value others may hold."""
        return [list(row) for row in self.get_value()]

    def _on_cell(self, row: int, col: int, e: Any) -> None:
        rows = self._rows()
        rows[row][col] = e.args if hasattr(e, "args") else e
        self.set_value(rows)

    def on_model_changed(self, value: Any) -> None:
        if value is None:
            return
        for row, cells in zip(value, getattr(self, "_cells", []), strict=False):
            for entry, cell in zip(row, cells, strict=False):
                cell.value = entry
