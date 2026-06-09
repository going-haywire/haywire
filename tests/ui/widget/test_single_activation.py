import haywire.core.graph.editor  # noqa: F401

import pytest
from typing import Any

from haywire.ui.widget.base import BaseWidget
from tests.ui.widget._sync_fixtures import make_float_port, _StandInElement

pytestmark = pytest.mark.unit


class _OneBind(BaseWidget):
    def build(self) -> Any:
        self.el = _StandInElement()
        return self.bind(self.el)


def test_render_subscribes_once_and_cleanup_removes_it():
    port = make_float_port()
    w = _OneBind(port)
    before = port._data.on_changed.handler_size
    w.render()
    after = port._data.on_changed.handler_size
    # exactly one dispatch subscription added (no double-activation)
    assert after - before == 1
    w.cleanup()
    assert port._data.on_changed.handler_size == before
    assert w._cleaned_up is True


def test_render_is_idempotent():
    port = make_float_port()
    w = _OneBind(port)
    w.render()
    n = port._data.on_changed.handler_size
    w.render()  # second call must not re-subscribe
    assert port._data.on_changed.handler_size == n
