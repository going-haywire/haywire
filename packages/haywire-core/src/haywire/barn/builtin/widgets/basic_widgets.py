"""
Basic widget implementations for common data types
"""

from typing import Any
from nicegui import ui

from haywire.ui.widget.decorator import widget
from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.converters import PrimitiveUnwrappingConverter
from haywire.ui.components.number.drag import NumberDrag


@widget(description="Fast number input widget")
class NumberWidget(BaseWidget):
    """
    Blender-style number input widget for float and int ports.

    Drag horizontally to change the value, click to type, or use
    the arrow buttons that appear on hover.

    Config options (via ``NumberWidget.config(properties={...})``):

    - ``min`` (int | float): Minimum allowed value.
    - ``max`` (int | float): Maximum allowed value.
    - ``step`` (int | float): Step increment for drag / arrows.
    - ``precision`` (int): Decimal places to display (-1 = auto from step).
    - ``prefix`` (str): Text shown before the value (e.g. ``'$'``).
    - ``suffix`` (str): Text shown after the value (e.g. ``'kg'``).
    - ``sensitivity`` (float): Drag sensitivity multiplier (default 1.0).

    Example::

        NumberWidget.config(properties={'min': 0, 'max': 200, 'step': 0.5})
    """

    def build(self) -> Any:
        props = self._config.get("properties", {})
        kwargs: dict[str, Any] = {"value": 0}

        for prop in ["min", "max", "step", "precision", "prefix", "suffix", "sensitivity"]:
            if prop in props:
                kwargs[prop] = props[prop]

        return self.bind(
            NumberDrag(**kwargs).classes("w-full"),
            converter=PrimitiveUnwrappingConverter(default_value=0.0),
        )


@widget(description="Fast text input widget")
class TextWidget(BaseWidget):
    """
    Text input widget for string ports.

    Config options (via ``TextWidget.config(properties={...})``):

    - ``label`` (str): Input label shown above the field.
    - ``placeholder`` (str): Placeholder text shown when the field is empty.
    - ``password`` (bool): If ``True``, input is masked as a password field.

    Example::

        TextWidget.config(properties={'label': 'Name', 'placeholder': 'Enter name...'})
    """

    def build(self) -> Any:
        props = self._config.get("properties", {})
        return self.bind(
            ui.input(
                value="",
                label=props.get("label", ""),
                placeholder=props.get("placeholder", ""),
                password=props.get("password", False),
            ).classes("w-full"),
            # NiceGUI's ``ui.input`` emits ``update:value`` for its value sync (not
            # the ``update:modelValue`` used by custom Vue components like NumberDrag
            # and Quasar passthroughs). Binding to the wrong event silently drops all
            # user edits in-browser, so the keystroke event must match the element.
            event="update:value",
            converter=PrimitiveUnwrappingConverter(default_value=""),
        )


@widget(description="checkbox widget")
class CheckboxWidget(BaseWidget):
    """
    Checkbox widget for boolean ports.

    Config options (via ``CheckboxWidget.config(properties={...})``):

    - ``text`` (str): Label text displayed next to the checkbox.

    Example::

        CheckboxWidget.config(properties={'text': 'Enable feature'})
    """

    def build(self) -> Any:
        props = self._config.get("properties", {})
        return self.bind(
            ui.checkbox(value=False, text=props.get("text", "")).classes("w-full"),
            converter=PrimitiveUnwrappingConverter(default_value=False),
        )


@widget(description="switch widget")
class SwitchWidget(BaseWidget):
    """
    Toggle switch widget for boolean ports.

    Config options (via ``SwitchWidget.config(properties={...})``):

    - ``text`` (str): Label text displayed next to the switch.

    Example::

        SwitchWidget.config(properties={'text': 'Active'})
    """

    def build(self) -> Any:
        props = self._config.get("properties", {})
        return self.bind(
            ui.switch(value=False, text=props.get("text", "")).classes("w-full text-xs"),
            converter=PrimitiveUnwrappingConverter(default_value=False),
        )


@widget(description="slider widget")
class SliderWidget(BaseWidget):
    """
    Horizontal slider widget for numeric ports.

    Config options (via ``SliderWidget.config(properties={...})``):

    - ``min`` (int | float): Minimum value (default: ``0``).
    - ``max`` (int | float): Maximum value (default: ``100``).
    - ``step`` (int | float): Step increment (default: ``1``).

    Example::

        SliderWidget.config(properties={'min': -1.0, 'max': 1.0, 'step': 0.01})
    """

    def build(self) -> Any:
        props = self._config.get("properties", {})
        kwargs: dict[str, Any] = {
            "value": 0,
            "min": props.get("min", 0),
            "max": props.get("max", 100),
            "step": props.get("step", 1),
        }

        default = float(props.get("min", 0))
        return self.bind(
            ui.slider(**kwargs).classes("w-full text-xs").props("label-always"),
            converter=PrimitiveUnwrappingConverter(default_value=default),
        )


@widget(description="select widget")
class SelectWidget(BaseWidget):
    """
    Dropdown select widget for int and string ports.

    Config options (via ``SelectWidget.config(properties={...})``):

    - ``options`` (list): List of selectable values or ``{value: label}`` dict (required).
    - ``clearable`` (bool): If ``True``, shows a clear button to reset the selection.
    - ``multiple`` (bool): If ``True``, allows selecting multiple values.

    Example::

        SelectWidget.config(properties={'options': ['Low', 'Medium', 'High']})
        SelectWidget.config(properties={'options': {0: 'Off', 1: 'On'}, 'clearable': True})
    """

    def build(self) -> Any:
        props = self._config.get("properties", {})
        kwargs: dict[str, Any] = {"options": props.get("options", []), "value": None}

        for prop in ["clearable", "multiple"]:
            if prop in props:
                kwargs[prop] = props[prop]

        return self.bind(ui.select(**kwargs).classes("w-full text-xs"))


@widget(description="Simple label for display only")
class SimpleLabelWidget(BaseWidget):
    """
    Read-only label widget that displays the port value as text.

    No configuration options — the label renders the raw value with no
    additional styling controls.

    Example::

        SimpleLabelWidget.config()
    """

    def build(self) -> Any:
        return self.bind(
            ui.label("").classes("text-base text-xs"),
            prop="text",
            one_way=True,
            converter=PrimitiveUnwrappingConverter(default_value=""),
        )
