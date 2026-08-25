"""ColorWidget — color picker for COLOR ports (and the COLOR setting type)."""

from typing import Any
from nicegui import ui

from haywire.ui.widget.decorator import widget
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.converters import PrimitiveUnwrappingConverter


@widget(description="Color picker widget")
class ColorWidget(BaseWidget):
    """Color picker widget for COLOR ports.

    Config options (via ``ColorWidget.config(properties={...})``):

    - ``alpha`` (bool): When ``True`` the picker edits and emits an 8-digit
      ``#rrggbbaa`` value instead of the 6-digit ``#rrggbb`` default. This is
      the opacity control — there is no separate opacity setting, because
      ``COLOR`` is a string type whose contract has always been "hex or rgba"
      (see ``ColorStr``), so the alpha rides inside the value itself.

    Quasar's QColor drives this through ``format-model``; ``hexa`` is the
    alpha-carrying counterpart of ``hex``. The default stays ``hex`` so every
    existing COLOR port is untouched.

    Example::

        ColorWidget.config(properties={'alpha': True})
    """

    def build(self) -> Any:
        alpha = bool(self._config.get("properties", {}).get("alpha", False))
        default = "#ffffffff" if alpha else "#ffffff"
        fmt = "hexa" if alpha else "hex"

        element = ui.color_input(value=default).classes("w-full").props("dense hide-bottom-space")
        # format-model belongs to the QColor itself. ColorInput nests it two
        # deep — `.picker` is the QMenu wrapper, `.picker.q_color` the QColor —
        # so neither the outer .props() above nor `.picker.props()` reaches it.
        element.picker.q_color.props(f"format-model={fmt}")

        # A pick in the popup does NOT reach the model through the binding's
        # `update:modelValue` listener: ColorInput wires the picker to a
        # *server-side* `self.set_value(...)`, and ValueElement.set_value never
        # emits the browser event the binding subscribes to. Only typing in the
        # input does. on_value_change fires for both paths, so the picker is
        # wired through it explicitly.
        self._element = element
        element.on_value_change(self._on_view_value_change)

        return self.bind(element, converter=PrimitiveUnwrappingConverter(default_value=default))

    def _on_view_value_change(self, event: Any) -> None:
        """Push a view value to the model, for changes the binding cannot see."""
        value = event.value
        if value is None or value == self.get_value():
            return
        self.set_value(value)

    def on_model_changed(self, value: Any) -> None:
        """Model → view sync, skipped when the view already holds *value*.

        Every edit here is a round trip — the view writes the model, the model
        change comes straight back — and writing a text-carrying input while
        the user is typing into it is what moves the caret. Suppressing the
        echo keeps the widget from disturbing the field it was just driven by.
        External writes (another panel, a mirror) still differ from the view
        and sync normally.

        NOTE: this is not the whole story for the properties panel. The four
        appearance props are in ``NodeProperties.REDRAW_FIELDS``, so each
        committed keystroke also rebuilds the entire node card — including this
        input. That focus loss is owned by the redraw path, not by this widget.
        """
        element = getattr(self, "_element", None)
        if element is not None and element.value == value:
            return
        super().on_model_changed(value)
