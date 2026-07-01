"""VecWidget — N-component numeric editor for VEC* ports.

Reads length + component labels from ``widget_config['properties']['vec_meta']``
(set by the VEC* type's ``widget_config``). Falls back to a single 3-component
group if absent.

Components stack vertically by default (one ``NumberDrag`` per row). Set
``properties['orientation'] = 'row'`` in the widget config to lay them out
horizontally instead.

Unlike the flat scalar widgets, a vector value is a list whose components are
edited independently, so this widget talks to the model directly via
``get_value()``/``set_value()`` rather than through ``bind()``.
"""

from typing import Any
from nicegui import ui

from haywire.ui.widget.decorator import widget
from haywire.ui.widget.base import BaseWidget
from haywire.ui.components.number.drag import NumberDrag


@widget(description="Vector component editor widget")
class VecWidget(BaseWidget):
    """N-component numeric editor for VEC* ports."""

    def build(self) -> Any:
        props = self._config.get("properties", {})
        meta = props.get("vec_meta", {})
        length = int(meta.get("length", 3))
        labels = meta.get("labels", [f"[{i}]" for i in range(length)])
        orientation = props.get("orientation", "column")

        current = self.get_value() or [0] * length
        self._fields: list[NumberDrag] = []
        # Column (default): one NumberDrag per row, full width, flush (gap-0).
        # Row: side by side with a small gap.
        container = ui.column if orientation == "column" else ui.row
        drag_classes = "w-full" if orientation == "column" else "flex-1"
        gap_class = "gap-0" if orientation == "column" else "gap-1"
        with container().classes(f"w-full {gap_class} no-wrap") as root:
            for i in range(length):
                val = current[i] if i < len(current) else 0
                drag = NumberDrag(
                    value=val,
                    prefix=f"{labels[i]} ",
                    on_change=lambda e, idx=i: self._on_component(idx, e),
                ).classes(drag_classes)
                self._fields.append(drag)
        return root

    def _on_component(self, idx: int, e: Any) -> None:
        vec = list(self.get_value() or [])
        while len(vec) <= idx:
            vec.append(0)
        vec[idx] = e.args if hasattr(e, "args") else e
        self.set_value(vec)

    def on_model_changed(self, value: Any) -> None:
        if not value:
            return
        for i, field in enumerate(getattr(self, "_fields", [])):
            if i < len(value):
                field.value = value[i]
