import pytest
from typing import Any

from haywire.ui.widget.base import BaseWidget
from tests.ui.widget._sync_fixtures import make_float_port, _RecordingElement

pytestmark = pytest.mark.unit


class _PrimitiveWidget(BaseWidget):
    def build(self) -> Any:
        self.el = _RecordingElement()
        return self.bind(self.el)  # to="value" default


class _ReadonlyWidget(BaseWidget):
    def build(self) -> Any:
        self.el = _RecordingElement()
        return self.bind(self.el, prop="text", one_way=True)


def test_primitive_bind_two_way_model_to_view():
    port = make_float_port()
    port.set_value(3.0)
    w = _PrimitiveWidget(port)
    w.render()
    assert w.el.value == 3.0
    port.set_value(5.0)
    assert w.el.value == 5.0


def test_primitive_bind_two_way_view_to_model():
    port = make_float_port()
    w = _PrimitiveWidget(port)
    w.render()
    w.el.value = 8.0
    handler = w.el.handlers["update:modelValue"]
    handler(type("E", (), {"sender": w.el})())  # fire the real view→model handler
    assert port.get_value() == 8.0


def test_readonly_bind_registers_no_view_to_model_handler():
    port = make_float_port()
    w = _ReadonlyWidget(port)
    w.render()
    # one_way=True must NOT wire a view→model handler. If one_way were ignored
    # (treated as two-way), the binding would register an update:modelValue handler.
    assert "update:modelValue" not in w.el.handlers


def test_two_way_bind_registers_view_to_model_handler():
    port = make_float_port()
    w = _PrimitiveWidget(port)  # default two-way
    w.render()
    assert "update:modelValue" in w.el.handlers
