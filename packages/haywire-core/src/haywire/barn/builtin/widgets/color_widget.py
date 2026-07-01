"""ColorWidget — color picker for COLOR ports (and the COLOR setting type)."""

from typing import Any
from nicegui import ui

from haywire.ui.widget.decorator import widget
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.converters import PrimitiveUnwrappingConverter


@widget(description="Color picker widget")
class ColorWidget(BaseWidget):
    """Color picker widget for COLOR ports."""

    def build(self) -> Any:
        return self.bind(
            ui.color_input(value="#ffffff").classes("w-full").props("dense hide-bottom-space"),
            converter=PrimitiveUnwrappingConverter(default_value="#ffffff"),
        )
