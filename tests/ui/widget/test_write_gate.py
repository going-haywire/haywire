"""A widget's write gate refuses a view edit at the write and snaps the view back."""

import pytest

from tests.ui.widget._sync_fixtures import _BaseDefaultFloatWidget, make_float_port

pytestmark = pytest.mark.unit


class _StubGate:
    """A write gate whose answer a test flips, counting the writes it was told about."""

    def __init__(self, allows: bool) -> None:
        self.allowed = allows
        self.written_calls = 0

    def allows(self) -> bool:
        return self.allowed

    def written(self) -> None:
        self.written_calls += 1


def _gated_widget(allows: bool):
    port = make_float_port()
    port.set_value(4.0)
    widget = _BaseDefaultFloatWidget(port)
    widget.render()
    gate = _StubGate(allows)
    widget.write_gate = gate
    return port, widget, gate


def test_a_refused_gate_snaps_the_view_back():
    port, widget, gate = _gated_widget(allows=False)
    widget.el.value = 9.0

    widget._bindings[0]._sync_to_model(9.0)

    assert port.data.get_own_value() == 4.0
    assert widget.el.value == 4.0
    assert gate.written_calls == 0


def test_a_refused_gate_blocks_set_value():
    port, widget, gate = _gated_widget(allows=False)
    widget.el.value = 9.0

    widget.set_value(9.0)

    assert port.data.get_own_value() == 4.0
    assert widget.el.value == 4.0
    assert widget.accepts_write() is False
    assert gate.written_calls == 0


def test_an_accepted_write_calls_written_once():
    port, widget, gate = _gated_widget(allows=True)

    widget._bindings[0]._sync_to_model(9.0)
    assert port.get_value() == 9.0
    assert gate.written_calls == 1

    widget.set_value(7.0)
    assert port.get_value() == 7.0
    assert gate.written_calls == 2


def test_writing_the_current_value_again_is_not_written():
    port, widget, gate = _gated_widget(allows=True)

    widget._bindings[0]._sync_to_model(4.0)
    widget.set_value(4.0)

    assert port.get_value() == 4.0
    assert gate.written_calls == 0


def test_a_gate_checked_at_write_time_not_at_render():
    port, widget, gate = _gated_widget(allows=True)
    gate.allowed = False

    widget._bindings[0]._sync_to_model(9.0)

    assert port.get_value() == 4.0


def test_no_gate_behaves_as_today():
    port = make_float_port()
    widget = _BaseDefaultFloatWidget(port)
    widget.render()

    assert widget.write_gate is None
    assert widget.accepts_write() is True
    widget._bindings[0]._sync_to_model(9.0)
    assert port.get_value() == 9.0
    widget.set_value(3.0)
    assert port.get_value() == 3.0


def test_a_linked_port_refuses_even_when_the_gate_allows():
    from typing import Any, cast

    port, widget, gate = _gated_widget(allows=True)
    port.incoming.linked["e1"] = cast(Any, object())
    port.set_value(5.0, edge_id="e1")

    assert widget.accepts_write() is False
    widget.set_value(9.0)
    assert port.data.get_own_value() == 4.0
    assert gate.written_calls == 0
