"""Regression: a widget must unsubscribe from the SAME DataField it subscribed to.

Promotion/demotion swaps ``port._data`` underneath a live widget:
``bind_field`` points the port at the setting's shared cell; ``unbind_field``
(called by demote) recreates a fresh private field. A widget that re-reads
``self.port.data`` at cleanup would then ``-=`` its dispatch cb from the WRONG
event object and raise ``ValueError: list.remove(x): x not in list``.

BaseWidget captures the field at render and unsubscribes from that same object,
so cleanup stays symmetric across the swap.
"""

import logging
from typing import Any

import pytest

from haywire.ui.widget.base import BaseWidget
from tests.ui.widget._sync_fixtures import make_float_port, _StandInElement

pytestmark = pytest.mark.unit


class _OneBind(BaseWidget):
    def build(self) -> Any:
        self.el = _StandInElement()
        return self.bind(self.el)


def test_cleanup_after_unbind_field_does_not_warn():
    """Simulate demote: port._data is swapped after render, before cleanup."""
    port = make_float_port()
    subscribed_field = port._data
    before = subscribed_field.on_changed.handler_size

    w = _OneBind(port)
    w.render()
    assert subscribed_field.on_changed.handler_size - before == 1

    # Demote recreates the port's field (port.unbind_field) → a different object.
    port.unbind_field()
    assert port._data is not subscribed_field

    # Cleanup must remove the cb from the field it actually subscribed to,
    # not from the swapped-in one — cleanly, without logging a failure.
    with _no_warning(BaseWidget):
        w.cleanup()

    assert subscribed_field.on_changed.handler_size == before
    assert w._cleaned_up is True


class _no_warning:
    """Assert the given class's module logger emits no WARNING during the block."""

    def __init__(self, cls: type) -> None:
        self._logger = logging.getLogger(cls.__module__)
        self._records: list[logging.LogRecord] = []

    def __enter__(self) -> "_no_warning":
        self._handler = logging.Handler()
        self._handler.emit = self._records.append  # type: ignore[method-assign,assignment]
        self._logger.addHandler(self._handler)
        return self

    def __exit__(self, *exc: Any) -> None:
        self._logger.removeHandler(self._handler)
        warnings = [r for r in self._records if r.levelno >= logging.WARNING]
        assert not warnings, f"unexpected warnings: {[r.getMessage() for r in warnings]}"
