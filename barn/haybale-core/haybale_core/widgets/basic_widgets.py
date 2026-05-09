"""
Basic widget implementations for common data types
"""

from typing import Any
from nicegui import ui

from haywire.ui.widget.decorator import widget
from haywire.ui.widget.simple import SimpleWidget
from haywire.ui.components.number.drag import NumberDrag

from haybale_core.types import BOOL, FLOAT, INT, STRING


@widget(description="Fast number input widget", compatible_types=[FLOAT, INT])
class NumberWidget(SimpleWidget):
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

    def create_element(self) -> Any:
        props = self._config.get("properties", {})
        kwargs: dict[str, Any] = {"value": 0}

        for prop in ["min", "max", "step", "precision", "prefix", "suffix", "sensitivity"]:
            if prop in props:
                kwargs[prop] = props[prop]

        return NumberDrag(**kwargs).classes("w-full")

    def get_default_value(self) -> float:
        return 0.0


@widget(description="Fast text input widget", compatible_types=[STRING])
class TextWidget(SimpleWidget):
    """
    Text input widget for string ports.

    Config options (via ``TextWidget.config(properties={...})``):

    - ``label`` (str): Input label shown above the field.
    - ``placeholder`` (str): Placeholder text shown when the field is empty.
    - ``password`` (bool): If ``True``, input is masked as a password field.

    Example::

        TextWidget.config(properties={'label': 'Name', 'placeholder': 'Enter name...'})
    """

    def create_element(self) -> Any:
        props = self._config.get("properties", {})
        kwargs = {"value": ""}

        for prop in ["label", "placeholder", "password"]:
            if prop in props:
                kwargs[prop] = props[prop]

        return ui.input(**kwargs).classes("w-full")

    def get_default_value(self) -> str:
        return ""


@widget(description="checkbox widget", compatible_types=[BOOL])
class CheckboxWidget(SimpleWidget):
    """
    Checkbox widget for boolean ports.

    Config options (via ``CheckboxWidget.config(properties={...})``):

    - ``text`` (str): Label text displayed next to the checkbox.

    Example::

        CheckboxWidget.config(properties={'text': 'Enable feature'})
    """

    def create_element(self) -> Any:
        props = self._config.get("properties", {})
        kwargs = {"value": False}

        if "text" in props:
            kwargs["text"] = props["text"]

        return ui.checkbox(**kwargs).classes("w-full")

    def get_default_value(self) -> bool:
        return False


@widget(description="switch widget", compatible_types=[BOOL])
class SwitchWidget(SimpleWidget):
    """
    Toggle switch widget for boolean ports.

    Config options (via ``SwitchWidget.config(properties={...})``):

    - ``text`` (str): Label text displayed next to the switch.

    Example::

        SwitchWidget.config(properties={'text': 'Active'})
    """

    def create_element(self) -> Any:
        props = self._config.get("properties", {})
        kwargs = {"value": False}

        if "text" in props:
            kwargs["text"] = props["text"]

        return ui.switch(**kwargs).classes("w-full text-xs")

    def get_default_value(self) -> bool:
        return False


@widget(description="slider widget", compatible_types=[FLOAT, INT])
class SliderWidget(SimpleWidget):
    """
    Horizontal slider widget for numeric ports.

    Config options (via ``SliderWidget.config(properties={...})``):

    - ``min`` (int | float): Minimum value (default: ``0``).
    - ``max`` (int | float): Maximum value (default: ``100``).
    - ``step`` (int | float): Step increment (default: ``1``).

    Example::

        SliderWidget.config(properties={'min': -1.0, 'max': 1.0, 'step': 0.01})
    """

    def create_element(self) -> Any:
        props = self._config.get("properties", {})
        kwargs = {
            "value": 0,
            "min": props.get("min", 0),
            "max": props.get("max", 100),
            "step": props.get("step", 1),
        }

        return ui.slider(**kwargs).classes("w-full text-xs").props("label-always")

    def get_default_value(self) -> float:
        props = self._config.get("properties", {})
        return float(props.get("min", 0))


@widget(description="select widget", compatible_types=[INT, STRING])
class SelectWidget(SimpleWidget):
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

    def create_element(self) -> Any:
        props = self._config.get("properties", {})
        kwargs = {"options": props.get("options", []), "value": None}

        for prop in ["clearable", "multiple"]:
            if prop in props:
                kwargs[prop] = props[prop]

        return ui.select(**kwargs).classes("w-full text-xs")


@widget(description="knob widget", compatible_types=[FLOAT, INT])
class KnobWidget(SimpleWidget):
    """
    Rotary knob widget for numeric ports.

    Config options (via ``KnobWidget.config(properties={...})``):

    - ``min`` (int | float): Minimum value.
    - ``max`` (int | float): Maximum value.
    - ``step`` (int | float): Step increment.
    - ``color`` (str): Quasar color name for the knob arc (e.g. ``'primary'``, ``'green'``).
    - ``size`` (str): CSS size of the knob element (e.g. ``'60px'``).

    Example::

        KnobWidget.config(properties={'min': 0, 'max': 360, 'step': 1, 'color': 'teal'})
    """

    def create_element(self) -> Any:
        props = self._config.get("properties", {})
        kwargs = {"value": 0, "show_value": True}

        for prop in ["min", "max", "step", "color", "size"]:
            if prop in props:
                kwargs[prop] = props[prop]

        with ui.row().classes("w-full justify-center text-xs"):
            knob = ui.knob(**kwargs)

        return knob.classes("w-32 h-32")

    def get_default_value(self) -> float:
        return 0.0


@widget(description="Simple label for display only", compatible_types=[STRING, FLOAT, INT])
class SimpleLabelWidget(SimpleWidget):
    """
    Read-only label widget that displays the port value as text.

    No configuration options — the label renders the raw value with no
    additional styling controls.

    Example::

        SimpleLabelWidget.config()
    """

    UI_PROPERTY = "text"
    IS_READONLY = True

    def create_element(self) -> Any:
        return ui.label("").classes("text-base text-xs")

    def get_default_value(self) -> str:
        return ""
