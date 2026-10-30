"""ButtonWidget: a click writes true; the button shows pending while the value is true."""

from __future__ import annotations

import pytest
from nicegui import ui

from haywire.barn.builtin.types import BOOL
from haywire.barn.builtin.widget_keys import BUTTON_WIDGET
from haywire.barn.builtin.widgets import ButtonWidget
from haywire.core.types.enums import PortType
from haywire.core.types.port import DataPort

pytestmark = pytest.mark.unit


def _port() -> DataPort:
    return DataPort(
        registry_id="run",
        registry_key=BOOL.class_identity.registry_key,
        label="Run",
        id="run",
        type_cls=BOOL,
        port_type=PortType.CONFIG,
        default={"value": False},
    )


def _render(port: DataPort) -> tuple[ButtonWidget, ui.element]:
    widget = ButtonWidget(port)
    return widget, widget.render()


def test_button_widget_key_matches_class() -> None:
    assert ButtonWidget.class_identity.registry_key == BUTTON_WIDGET


def test_click_writes_true(nicegui_slot_context) -> None:
    port = _port()
    widget, _root = _render(port)

    widget._on_click()

    assert port.get_value() is True


def test_pending_follows_model(nicegui_slot_context) -> None:
    port = _port()
    widget, _root = _render(port)
    assert not widget._button._props.get("loading")

    port.set_value(True)
    assert widget._button._props.get("loading")

    port.set_value(False)
    assert not widget._button._props.get("loading")


def test_refused_write_shows_model_value(nicegui_slot_context, monkeypatch) -> None:
    port = _port()
    widget, _root = _render(port)
    monkeypatch.setattr(port, "set_value", lambda value: False)

    widget._on_click()

    assert port.get_value() is False
    assert not widget._button._props.get("loading")
