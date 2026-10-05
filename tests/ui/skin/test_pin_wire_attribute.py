"""Every pin tells the canvas its wire key, and a ghost pin says it is one."""

import pytest

from haywire.barn.builtin.types import ADD, FLOAT
from haywire.barn.builtin.wires import DataWire
from haywire.core.types import DataPort, PortType
from haywire.core.types.enums import LayoutDirection
from haywire.ui.skin.pin_render import render_ghost_pin, render_pin

pytestmark = pytest.mark.unit


def _port(type_cls) -> DataPort:
    return DataPort(
        registry_id="p",
        registry_key=type_cls.class_identity.registry_key,
        label="P",
        id="p",
        type_cls=type_cls,
        port_type=PortType.INLET,
    )


def _render(port):
    return render_pin(port, "node-1", pin_gutter=20, card_padding=16, pin_protrusion=0)


def test_a_typed_pin_carries_its_wire_types_id(nicegui_slot_context):
    props = _render(_port(FLOAT))._props
    assert props.get("data-pin-wire") == DataWire.id
    assert "data-pin-flow-type" not in props
    assert "data-pin-any-flow" not in props


def test_a_bare_add_pin_carries_the_wildcard(nicegui_slot_context):
    assert _render(_port(ADD))._props.get("data-pin-wire") == "*"


def test_a_ghost_pin_is_marked_and_carries_no_wire(nicegui_slot_context):
    ghost = render_ghost_pin("node-1", layout=LayoutDirection.LEFT_TO_RIGHT, is_inlet=True, offset=8)
    assert "data-pin-ghost" in ghost._props
    assert "data-pin-wire" not in ghost._props
