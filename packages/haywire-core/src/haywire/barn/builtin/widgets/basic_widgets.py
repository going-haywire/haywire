"""
Basic widget implementations for common data types
"""

from typing import Any
from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.modals import text_modal
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

    An inline single-line input plus an expand-to-modal button: the button pops
    out a full-size ``autogrow`` textarea (``text_modal``) for editing long or
    multi-line values, writing the confirmed text back through the port cell so
    the inline input re-syncs automatically.

    Config options (via ``TextWidget.config(properties={...})``):

    - ``label`` (str): Input label shown above the field.
    - ``placeholder`` (str): Placeholder text shown when the field is empty.
    - ``password`` (bool): If ``True``, input is masked as a password field.

    Example::

        TextWidget.config(properties={'label': 'Name', 'placeholder': 'Enter name...'})
    """

    def build(self) -> Any:
        props = self._config.get("properties", {})
        self._label: str = props.get("label", "")
        self._placeholder: str = props.get("placeholder", "")

        # The row is the widget root; the bound input is the model→view target,
        # so binding still drives the input exactly as before. The expand button
        # is chrome beside it (view-only — it writes through set_value on confirm).
        with ui.row().classes("w-full flex-nowrap items-center gap-1") as root:
            self.bind(
                ui.input(
                    value="",
                    label=self._label,
                    placeholder=self._placeholder,
                    password=props.get("password", False),
                ).classes("flex-1 min-w-0"),
                # NiceGUI's ``ui.input`` emits ``update:value`` for its value sync (not
                # the ``update:modelValue`` used by custom Vue components like NumberDrag
                # and Quasar passthroughs). Binding to the wrong event silently drops all
                # user edits in-browser, so the keystroke event must match the element.
                event="update:value",
                converter=PrimitiveUnwrappingConverter(default_value=""),
            )
            ui.button(icon=hui.icon.expand_full, on_click=self._open_modal).props(
                "flat dense size=xs"
            ).tooltip("Edit in full")
        return root

    def _open_modal(self) -> None:
        """Open the full-size text editor, seeded from the current value.

        Confirm writes through ``set_value`` (the port cell); the inline input
        re-syncs via the widget's own model→view dispatch — no mirror state."""
        value = self.get_value()
        text_modal(
            title=self._label or "Edit text",
            value="" if value is None else str(value),
            placeholder=self._placeholder,
            on_confirm=self.set_value,
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

    - ``options`` (list, ``{value: label}`` dict, or zero-arg callable returning
      either): List of selectable values (required). A callable is invoked fresh
      at every ``build()`` — options can reflect state that changed since the
      setting/port was declared (e.g. available theme skins).
    - ``clearable`` (bool): If ``True``, shows a clear button to reset the selection.
    - ``multiple`` (bool): If ``True``, allows selecting multiple values.

    Example::

        SelectWidget.config(properties={'options': ['Low', 'Medium', 'High']})
        SelectWidget.config(properties={'options': {0: 'Off', 1: 'On'}, 'clearable': True})
        SelectWidget.config(properties={'options': lambda: list_available_skins()})
    """

    def build(self) -> Any:
        props = self._config.get("properties", {})
        options = props.get("options", [])
        # Resolve callable options at build time for dynamic option lists
        if callable(options):
            options = options()

        kwargs: dict[str, Any] = {"options": options, "value": None}

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
