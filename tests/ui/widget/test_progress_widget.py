"""ProgressWidget: an empty bar while idle, a sweep while busy without a fraction, a fill with one."""

from __future__ import annotations

import pytest
from nicegui import ui

from haywire.barn.builtin.types import PROGRESS
from haywire.barn.builtin.widgets.progress_widget import ProgressWidget
from haywire.core.types.enums import PortType
from haywire.core.types.port import DataPort

pytestmark = pytest.mark.unit


def _port() -> DataPort:
    return DataPort(
        registry_id="progress",
        registry_key=PROGRESS.class_identity.registry_key,
        label="Progress",
        id="progress",
        type_cls=PROGRESS,
        port_type=PortType.CONFIG,
    )


def _render(port: DataPort) -> tuple[ProgressWidget, ui.element]:
    widget = ProgressWidget(port)
    return widget, widget.render()


def test_idle_shows_an_empty_bar(nicegui_slot_context) -> None:
    widget, root = _render(_port())

    assert root._props["data-hw-progress"] == "idle"
    assert widget._fill._style["width"] == "0%"
    assert widget._label.text == " "


def test_busy_without_fraction_sweeps(nicegui_slot_context) -> None:
    port = _port()
    widget, root = _render(port)

    port.set_value(PROGRESS(active=True, label="inferring"))

    assert root._props["data-hw-progress"] == "busy"
    assert "hw-progress-sweep" in widget._fill._classes
    assert widget._label.text == "inferring"


def test_fraction_fills_the_bar(nicegui_slot_context) -> None:
    port = _port()
    widget, _root = _render(port)

    port.set_value(PROGRESS(active=True, fraction=0.4, label="tiles"))

    assert widget._fill._style["width"] == "40.0%"
    assert "hw-progress-sweep" not in widget._fill._classes


def test_back_to_idle_clears_the_label(nicegui_slot_context) -> None:
    port = _port()
    widget, root = _render(port)
    port.set_value(PROGRESS(active=True, fraction=0.4, label="tiles"))

    port.set_value(PROGRESS())

    assert root._props["data-hw-progress"] == "idle"
    assert widget._label.text == " "
