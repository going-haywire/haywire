import pytest
from dataclasses import dataclass
from typing import Any

from haywire.core.types.base import BaseType
from haywire.core.types.port import DataPort
from haywire.core.types.enums import FlowType, PortType
from haywire.ui.widget.base import BaseWidget
from tests.ui.widget._sync_fixtures import _RecordingElement

pytestmark = pytest.mark.unit


@dataclass
class _Vec2(BaseType):
    x: float = 0.0
    y: float = 0.0


def _vec2_port() -> DataPort:
    return DataPort(
        registry_id="vec2",
        registry_key="test:type:vec2",
        label="V",
        id="v",
        type_cls=_Vec2,
        port_type=PortType.INLET,
        flow_type=FlowType.DATA,
    )


class _Vec2Widget(BaseWidget):
    def build(self) -> Any:
        self.ex = _RecordingElement()
        self.ey = _RecordingElement()
        self.bind(self.ex, to="x")
        self.bind(self.ey, to="y")
        return self.ex


def test_nested_field_path_model_to_view():
    port = _vec2_port()
    port.set_value(_Vec2(x=1.0, y=2.0))
    w = _Vec2Widget(port)
    w.render()
    assert w.ex.value == 1.0
    assert w.ey.value == 2.0


def test_nested_field_path_model_to_view_update():
    """Model change after initial render propagates to both sub-elements."""
    port = _vec2_port()
    port.set_value(_Vec2(x=1.0, y=2.0))
    w = _Vec2Widget(port)
    w.render()
    port.set_value(_Vec2(x=7.0, y=9.0))
    assert w.ex.value == 7.0
    assert w.ey.value == 9.0


def test_nested_field_path_view_to_model():
    """bind(to='x') view→model path: writing the element fires _update_nested_property."""
    port = _vec2_port()
    port.set_value(_Vec2(x=0.0, y=0.0))
    w = _Vec2Widget(port)
    w.render()

    # Find the binding that owns source_property="x"
    x_binding = next(b for b in w._bindings if b.source_property == "x")

    # Simulate the view→model path: set the element's value then fire the handler
    w.ex.value = 9.0
    handler = w.ex.handlers["update:modelValue"]
    handler(type("E", (), {"sender": w.ex})())

    assert port.get_value().x == 9.0  # type: ignore[union-attr]
    # y must remain untouched
    assert port.get_value().y == 0.0  # type: ignore[union-attr]
    # binding is the right one
    assert x_binding.source_property == "x"
