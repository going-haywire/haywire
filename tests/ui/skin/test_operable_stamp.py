"""Every card widget the skin funnel draws is marked operable; a pin with its own tooltip is readable."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from nicegui import ui

from haywire.ui.skin.base import BaseSkin
from haywire.ui.skin.pin_render import add_pin_tooltip

pytestmark = pytest.mark.unit


class _Skin(BaseSkin):
    def render(self, main_card, wrapper, *, on_stage):  # pragma: no cover - not drawn here
        raise NotImplementedError


def test_render_widget_stamps_operable(nicegui_slot_context) -> None:
    element = ui.element("div")
    factory = MagicMock()
    factory.render_widget.return_value = (None, element)
    port = SimpleNamespace(id="value", widget_key="lib:widget:Number")

    returned = _Skin(factory).render_widget(port, "node-1")  # type: ignore[arg-type]

    assert returned is element
    assert "data-hw-operable" in element._props


def test_a_port_without_a_widget_renders_nothing(nicegui_slot_context) -> None:
    port = SimpleNamespace(id="value", widget_key=None)
    assert _Skin(MagicMock()).render_widget(port, "node-1") is None  # type: ignore[arg-type]


def test_a_pin_triggering_its_own_tooltip_is_readable(nicegui_slot_context) -> None:
    pin_el = ui.element("i")
    add_pin_tooltip(pin_el, SimpleNamespace(label="Gain", description=""))  # type: ignore[arg-type]
    assert "data-hw-readable" in pin_el._props


def test_a_separate_tooltip_trigger_keeps_its_own_rule(nicegui_slot_context) -> None:
    host = ui.element("div")
    trigger = ui.element("div")
    add_pin_tooltip(host, SimpleNamespace(label="Gain", description=""), trigger_el=trigger)  # type: ignore[arg-type]
    assert "data-hw-readable" not in host._props
    assert "data-hw-readable" not in trigger._props


def test_a_non_operable_widget_is_not_stamped(nicegui_slot_context) -> None:
    element = ui.element("div")
    factory = MagicMock()
    factory.render_widget.return_value = (None, element)
    port = SimpleNamespace(id="text", widget_key="lib:widget:Text", operable=False)

    returned = _Skin(factory).render_widget(port, "node-1")  # type: ignore[arg-type]

    assert returned is element
    assert "data-hw-operable" not in element._props
