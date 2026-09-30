"""A bare ADD pin tells the canvas it accepts any flow."""

import pytest

from haywire.barn.builtin.types import ADD, FLOAT
from haywire.core.types import DataPort, FlowType, PortType
from haywire.ui.skin.pin_render import render_pin

pytestmark = pytest.mark.unit


def _port(type_cls) -> DataPort:
    return DataPort(
        registry_id="p",
        registry_key=type_cls.class_identity.registry_key,
        label="P",
        id="p",
        type_cls=type_cls,
        port_type=PortType.INLET,
        flow_type=FlowType.DATA,
    )


def _render(port):
    return render_pin(port, "node-1", pin_gutter=20, card_padding=16, pin_protrusion=0)


def test_a_bare_add_pin_accepts_any_flow(nicegui_slot_context):
    assert _render(_port(ADD))._props.get("data-pin-any-flow") == "true"


def test_a_typed_pin_does_not(nicegui_slot_context):
    assert "data-pin-any-flow" not in _render(_port(FLOAT))._props
