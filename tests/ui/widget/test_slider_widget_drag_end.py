"""SliderWidget writes the value a drag ends on.

``ui.slider`` updates its own ``value`` through a 50 ms throttle, so during a fast
drag the binding's per-event read of ``value`` lags the thumb and the last
position can be lost. Quasar's ``change`` event, sent once when the drag ends,
carries the final value.
"""

from typing import Any, cast

import pytest
from nicegui import Client

from haywire.barn.builtin.types import FLOAT, INT
from haywire.barn.builtin.widgets import SliderWidget
from haywire.ui.panel.setting_widget_model import SettingWidgetModel

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _rendered(item_type: Any, initial: Any):
    cell = item_type.create_field(default_override={"value": initial})
    model = SettingWidgetModel(
        field_id="slider",
        widget_config={"properties": {"min": 0, "max": 10, "step": 1}},
        cell=cell,
        on_edit=cell.set_value,
    )
    widget = cast(Any, SliderWidget(model))
    with Client(cast(Any, _noop_page), request=None):
        widget.render()
    return widget, cell


def _fire(element: Any, event: str, args: Any) -> None:
    listener = next(lst for lst in element._event_listeners.values() if lst.type == event)
    element._handle_event({"listener_id": listener.id, "args": args})


def test_the_drag_end_value_reaches_the_model_while_the_element_lags():
    widget, cell = _rendered(FLOAT, 2.0)
    # The throttled update has not reached the element yet: it still holds 2.0.
    _fire(widget.ui_element, "change", 9.0)
    assert cell.get_value() == 9.0


def test_an_int_slider_stores_an_int():
    widget, cell = _rendered(INT, 2)
    _fire(widget.ui_element, "change", 7.0)
    assert cell.get_value() == 7
    assert type(cell.get_value()) is int
