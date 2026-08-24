"""NumberWidget bound to an INT port must render without a decimal point.

NumberDrag's own "auto" precision (-1) derives decimal places from `step`
alone, so a bare INT port (default step 0.1) would otherwise still show one
decimal digit (e.g. "5.0"). NumberWidget.build() special-cases INT-stored
ports to default precision=0, unless the caller explicitly configured one.
"""

import pytest
from nicegui import ui

from haywire.barn.builtin.types import FLOAT, INT
from haywire.barn.builtin.widgets.basic_widgets import NumberWidget
from haywire.core.types.enums import FlowType, PortType
from haywire.core.types.port import DataPort

pytestmark = pytest.mark.unit


def _make_port(type_cls, widget_config: dict | None = None) -> DataPort:
    return DataPort(
        registry_id="n",
        registry_key="haybale_core:type:n",
        label="N",
        id="v",
        type_cls=type_cls,
        port_type=PortType.INLET,
        flow_type=FlowType.DATA,
        widget_config=widget_config or {},
    )


def test_int_port_defaults_to_zero_precision(nicegui_slot_context):
    with ui.card():
        port = _make_port(INT)
        w = NumberWidget(port)
        el = w.render()
    assert el._props["precision"] == 0


def test_float_port_keeps_auto_precision(nicegui_slot_context):
    with ui.card():
        port = _make_port(FLOAT)
        w = NumberWidget(port)
        el = w.render()
    assert el._props["precision"] == -1


def test_explicit_precision_overrides_int_default(nicegui_slot_context):
    with ui.card():
        port = _make_port(INT, widget_config={"properties": {"precision": 2}})
        w = NumberWidget(port)
        el = w.render()
    assert el._props["precision"] == 2
