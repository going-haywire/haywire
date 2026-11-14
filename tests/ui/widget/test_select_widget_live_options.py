"""SelectWidget with callable ``options``: re-read on every dropdown open, optionally from the bag."""

from typing import Any, cast

import pytest
from nicegui import Client, events

from haywire.barn.builtin.types import STRING
from haywire.barn.builtin.widgets.basic_widgets import SelectWidget
from haywire.ui.panel.setting_widget_model import SettingWidgetModel

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _rendered(properties: dict[str, Any], value: str = "a", settings: Any = None):
    """A SelectWidget on a STRING cell; returns widget, cell, client."""
    cell = STRING.create_field(default_override={"value": value})
    config = {"properties": properties}
    model = SettingWidgetModel(
        field_id="choice", widget_config=config, cell=cell, on_edit=cell.set_value, settings=settings
    )
    widget = SelectWidget(model)
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        widget.render()
    return cast(Any, widget), cell, client


def _refreshers(widget: Any) -> list:
    """The widget's own ``popup-show`` listeners (NiceGUI stores the event camel-cased, beside its own)."""
    return [
        lis
        for lis in widget.ui_element._event_listeners.values()
        if lis.type == "popupShow" and getattr(lis.handler, "__name__", "") == "_refresh_options"
    ]


def _open_dropdown(widget: Any, client: Client) -> None:
    """Send what Quasar sends when the user opens the dropdown."""
    with client:
        for listener in _refreshers(widget):
            args = events.GenericEventArguments(sender=widget.ui_element, client=client, args=None)
            events.handle_event(listener.handler, args)


def test_callable_options_are_read_again_when_the_dropdown_opens():
    found = ["a", "b"]
    widget, _, client = _rendered({"options": lambda: list(found)})
    assert widget.ui_element.options == ["a", "b"]

    found.append("c")
    _open_dropdown(widget, client)

    assert widget.ui_element.options == ["a", "b", "c"]


def test_the_current_value_stays_listed_when_the_new_options_lack_it():
    found = ["a", "b"]
    widget, cell, client = _rendered({"options": lambda: list(found)}, value="a")

    found[:] = ["b"]
    _open_dropdown(widget, client)

    assert widget.ui_element.options == ["b", "a"]
    assert widget.ui_element.value == "a"
    assert cell.get_value() == "a"


def test_the_current_value_stays_listed_in_dict_options():
    found = {"a": "A", "b": "B"}
    widget, _, client = _rendered({"options": lambda: dict(found)}, value="a")

    del found["a"]
    _open_dropdown(widget, client)

    assert widget.ui_element.options == {"b": "B", "a": "a"}
    assert widget.ui_element.value == "a"


def test_a_one_argument_callable_receives_the_settings_bag():
    bag = type("Bag", (), {"backend": "syphon"})()
    sources = {"ndi": ["n1"], "syphon": ["s1", "s2"]}
    widget, _, client = _rendered({"options": lambda b: sources[b.backend]}, value="s1", settings=bag)
    assert widget.ui_element.options == ["s1", "s2"]

    bag.backend = "ndi"
    _open_dropdown(widget, client)

    assert widget.ui_element.options == ["n1", "s1"]  # the current value stays listed


def test_a_one_argument_callable_gets_none_without_a_bag():
    seen: list = []

    def options(bag: Any) -> list[str]:
        seen.append(bag)
        return ["a"]

    _rendered({"options": options})
    assert seen == [None]


def test_a_bag_parameter_with_a_default_also_receives_the_bag():
    # The spelling a library uses to work with a framework that calls options() bare.
    def options(bag: Any = None) -> list[str]:
        return ["all"] if bag is None else [bag.backend]

    bag = type("Bag", (), {"backend": "omt"})()
    widget, _, _ = _rendered({"options": options}, value="omt", settings=bag)
    assert widget.ui_element.options == ["omt"]


def test_a_callable_without_parameters_is_called_bare():
    widget, _, _ = _rendered({"options": lambda: ["a"]}, settings=object())
    assert widget.ui_element.options == ["a"]


def test_static_options_are_not_refreshed():
    widget, _, _ = _rendered({"options": ["a", "b"]})
    assert _refreshers(widget) == []
