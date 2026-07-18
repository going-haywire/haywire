import pytest
from typing import Any

from haywire.ui.widget.base import BaseWidget
from tests.ui.widget._sync_fixtures import make_float_port, _StandInElement

pytestmark = pytest.mark.unit


class _FloorWidget(BaseWidget):
    """Floor-only widget: no bind(), records every model change."""

    def __init__(self, port):
        super().__init__(port)
        self.seen: list[Any] = []

    def build(self) -> Any:
        return _StandInElement()

    def on_model_changed(self, value: Any) -> None:
        self.seen.append(value)


def test_on_model_changed_fires_on_port_change_and_at_render():
    port = make_float_port()
    port.set_value(7.0)
    w = _FloorWidget(port)
    w.render()
    assert w.seen[-1] == 7.0  # initial sync at render
    port.set_value(9.0)
    assert w.seen[-1] == 9.0  # subsequent change dispatched
