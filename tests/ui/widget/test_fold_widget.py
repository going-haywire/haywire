"""FoldWidget: the fold's header, whose click writes the opposite open state through its model."""

from __future__ import annotations

from typing import Any

import pytest
from nicegui import ui

from haywire.barn.builtin.types import FOLD
from haywire.barn.builtin.widgets.fold_widget import FoldWidget
from haywire.core.types.enums import PortType
from haywire.core.types.port import DataPort
from haywire.ui import elements as hui
from haywire.ui.panel.setting_widget_model import SettingWidgetModel

pytestmark = pytest.mark.unit


def _model(value: bool, on_edit) -> SettingWidgetModel:
    port = DataPort(
        registry_id="solver",
        registry_key=FOLD.class_identity.registry_key,
        label="Solver",
        id="solver",
        type_cls=FOLD,
        port_type=PortType.CONFIG,
    )
    port.data.set_value(value)
    return SettingWidgetModel(
        field_id="solver",
        widget_config={"properties": {"text": "Solver"}},
        cell=port.data,
        on_edit=on_edit,
    )


def _click(root: ui.element) -> None:
    listener = next(lis for lis in root._event_listeners.values() if lis.type == "click")
    assert listener.handler is not None
    listener.handler()


def _icons(root: ui.element) -> list[Any]:
    return [e._props.get("name") for e in root.descendants() if isinstance(e, ui.icon)]


def test_a_click_writes_the_opposite_value(nicegui_slot_context) -> None:
    writes: list[Any] = []
    root = FoldWidget(_model(True, writes.append)).render()

    _click(root)

    assert writes == [False]


def test_a_refused_click_shows_the_model_again(nicegui_slot_context) -> None:
    root = FoldWidget(_model(True, lambda _v: False)).render()

    _click(root)

    assert root._props["data-hw-fold-open"] == "true"
    assert _icons(root) == [hui.icon.fold_open, hui.icon.checked]


def test_the_header_shows_the_label_and_state(nicegui_slot_context) -> None:
    root = FoldWidget(_model(False, lambda _v: None)).render()

    assert root._props["data-hw-fold-id"] == "solver"
    assert root._props["data-hw-fold-open"] == "false"
    assert [e.text for e in root.descendants() if isinstance(e, ui.label)] == ["Solver"]
    assert _icons(root) == [hui.icon.fold_closed, hui.icon.unchecked]


def test_an_accepted_write_updates_the_header(nicegui_slot_context) -> None:
    holder: list[SettingWidgetModel] = []
    model = _model(True, lambda v: holder[0].data.set_value(v))
    holder.append(model)
    root = FoldWidget(model).render()

    _click(root)

    assert root._props["data-hw-fold-open"] == "false"
    assert _icons(root) == [hui.icon.fold_closed, hui.icon.unchecked]


def test_only_the_triangle_triggers_the_tooltip(nicegui_slot_context) -> None:
    root = FoldWidget(_model(True, lambda _v: None)).render()
    hovered = [
        e
        for e in [root, *root.descendants()]
        if any(lis.type == "mouseenter" for lis in e._event_listeners.values())
    ]
    assert len(hovered) == 1
    assert isinstance(hovered[0], ui.icon)
    assert hovered[0]._props["name"] == hui.icon.fold_open
