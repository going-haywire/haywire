"""
Blender-style drag number input.

Features:
- Horizontal drag to change value
- Left / right arrow buttons (visible on hover)
- Single click or double-click to enter text-edit mode
- Configurable min, max, step, precision, prefix, suffix
"""

from typing import Any, Callable, Optional

from nicegui import ui


class NumberDrag(ui.element, component='number_drag.vue'):
    """Blender-style number input with drag-to-change, arrow buttons, and inline editing."""

    def __init__(
        self,
        value: float = 0,
        *,
        min: float = float('-inf'),
        max: float = float('inf'),
        step: float = 0.1,
        precision: int = -1,
        prefix: str = '',
        suffix: str = '',
        sensitivity: float = 1.0,
        on_change: Optional[Callable[..., Any]] = None,
    ) -> None:
        super().__init__()
        self._props['model-value'] = value
        self._props['min'] = min
        self._props['max'] = max
        self._props['step'] = step
        self._props['precision'] = precision
        self._props['prefix'] = prefix
        self._props['suffix'] = suffix
        self._props['sensitivity'] = sensitivity

        self._change_handler = on_change

        def handle_update(e):
            self._props['model-value'] = e.args
            self.update()
            if self._change_handler is not None:
                self._change_handler(e)

        self.on('update:modelValue', handle_update)

    @property
    def value(self) -> float:
        return self._props.get('model-value', 0)

    @value.setter
    def value(self, v: float) -> None:
        self._props['model-value'] = v
        self.update()
