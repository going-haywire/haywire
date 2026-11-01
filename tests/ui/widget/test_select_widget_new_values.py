"""SelectWidget with ``new_value_mode``: typed values are kept, the declared options never change."""

from typing import Any, cast

import pytest
from nicegui import Client, events

from haywire.barn.builtin.types import STRING
from haywire.barn.builtin.widgets.basic_widgets import SelectWidget
from haywire.ui.panel.setting_widget_model import SettingWidgetModel

pytestmark = pytest.mark.integration

OPTIONS = ["auto", "cpu", "cu126"]


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _rendered(properties: dict[str, Any], value: str = "auto"):
    """A SelectWidget on a STRING cell whose edits land in the cell; returns widget, cell, config, client."""
    cell = STRING.create_field(default_override={"value": value})

    def on_edit(new: Any) -> None:
        cell.set_value(new)

    config = {"properties": properties}
    model = SettingWidgetModel(field_id="choice", widget_config=config, cell=cell, on_edit=on_edit)
    widget = SelectWidget(model)
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        widget.render()
    return cast(Any, widget), cell, config, client


def _type_new_value(widget: Any, client: Client, text: str) -> None:
    """Send what Quasar sends when the user types *text* and presses Enter: the bare string."""
    element = widget.ui_element
    with client:
        for listener in list(element._event_listeners.values()):
            if listener.type == "update:modelValue":
                args = events.GenericEventArguments(sender=element, client=client, args=text)
                events.handle_event(listener.handler, args)


def test_new_value_mode_reaches_the_select():
    widget, _, _, _ = _rendered({"options": OPTIONS, "new_value_mode": "add-unique"})
    assert widget.ui_element.props["new-value-mode"] == "add-unique"
    assert widget.ui_element.props["use-input"] is True


def test_a_typed_value_is_stored_and_the_declared_options_stay_unchanged():
    widget, cell, config, client = _rendered({"options": list(OPTIONS), "new_value_mode": "add-unique"})
    _type_new_value(widget, client, "cu124")
    assert cell.get_value() == "cu124"
    assert widget.ui_element.value == "cu124"
    assert "cu124" in widget.ui_element.options
    assert config["properties"]["options"] == OPTIONS


def test_a_stored_value_that_is_not_an_option_is_shown():
    widget, _, config, _ = _rendered({"options": list(OPTIONS), "new_value_mode": "add-unique"}, "rocm6.4")
    assert widget.ui_element.value == "rocm6.4"
    assert widget.ui_element.options == [*OPTIONS, "rocm6.4"]
    assert config["properties"]["options"] == OPTIONS


def test_a_model_change_to_a_value_that_is_not_an_option_is_shown():
    widget, cell, config, _ = _rendered({"options": list(OPTIONS), "new_value_mode": "add-unique"})
    cell.set_value("xpu")  # undo, paste, a write from elsewhere
    assert widget.ui_element.value == "xpu"
    assert config["properties"]["options"] == OPTIONS


def test_dict_options_get_the_value_as_its_own_label():
    widget, _, config, _ = _rendered({"options": {"auto": "Auto"}, "new_value_mode": "add-unique"}, "cpu")
    assert widget.ui_element.options == {"auto": "Auto", "cpu": "cpu"}
    assert config["properties"]["options"] == {"auto": "Auto"}


def test_without_new_value_mode_the_options_are_left_alone():
    widget, _, _, _ = _rendered({"options": list(OPTIONS)}, "other")
    assert widget.ui_element.options == OPTIONS
    assert "new-value-mode" not in widget.ui_element.props
