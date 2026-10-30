"""Run Button: a press on its button triggers its listeners once, while the graph runs."""

import threading
import time
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from haywire.barn.builtin.widget_keys import BUTTON_WIDGET
from haywire.core.graph.base import BaseGraph
from haywire.core.types.enums import PortType

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _button(graph: BaseGraph) -> Any:
    from haybale_core.nodes.emits.run_button import RunButtonNode

    wrapper = make_node(graph, RunButtonNode.class_identity.registry_key)
    assert isinstance(wrapper.node, RunButtonNode), "an unknown key yields an ErrorNode"
    return wrapper.node


def _listen(node: Any, *names: str) -> None:
    """Make the node emit to ``names``, as if Tick Events were wired to its Trigger inlet."""
    value = node.value

    def patched(port_id: str) -> Any:
        if port_id == "callbacks":
            return {name: name for name in names}
        return value(port_id)

    node.value = patched


def _context(control_pin: str, calls: list) -> SimpleNamespace:
    return SimpleNamespace(
        control_pin=control_pin,
        emit_callback=lambda event_name, payload=None: calls.append((event_name, payload)),
    )


def _wait_for(predicate: Callable[[], bool], timeout_s: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


@pytest.fixture
def button(graph_with_library_system):
    node = _button(graph_with_library_system)
    yield node
    node.on_teardown()


def test_promoted_as_config_with_button_widget(button):
    port = button.ports["button.run"]
    assert port.port_type is PortType.CONFIG
    assert port.widget_key == BUTTON_WIDGET


def test_press_emits_once_to_every_callback(button):
    calls: list = []
    _listen(button, "tick_a", "tick_b")
    assert button.worker(_context("start", calls)) == "started"

    button.button.run = True

    assert sorted(calls) == [("tick_a", {"delta_time": 0.0}), ("tick_b", {"delta_time": 0.0})]
    assert _wait_for(lambda: button.button.run is False)
    assert len(calls) == 2


def test_second_press_reports_time_since_previous(button):
    calls: list = []
    _listen(button, "tick")
    button.worker(_context("start", calls))

    button.button.run = True
    assert _wait_for(lambda: button.button.run is False)
    time.sleep(0.06)
    button.button.run = True

    assert len(calls) == 2
    assert calls[1][1]["delta_time"] >= 0.05


def test_release_goes_through_post_value(button, monkeypatch):
    calls: list = []
    posted: list = []
    _listen(button, "tick")
    button.worker(_context("start", calls))
    monkeypatch.setattr(button, "post_value", lambda port_id, value: posted.append((port_id, value)))

    button.button.run = True

    assert posted == [("button.run", False)]


def test_press_before_release_does_not_emit_again(button, monkeypatch):
    calls: list = []
    _listen(button, "tick")
    button.worker(_context("start", calls))
    monkeypatch.setattr(button, "post_value", lambda port_id, value: None)

    button.button.run = True
    button.button.run = True

    assert len(calls) == 1


def test_start_clears_a_stale_press(button):
    calls: list = []
    _listen(button, "tick")
    button.button.run = True

    button.worker(_context("start", calls))

    assert calls == []
    assert button.button.run is False


def test_press_while_stopped_emits_nothing(button):
    calls: list = []
    _listen(button, "tick")

    button.button.run = True
    time.sleep(0.1)

    assert calls == []
    assert button.button.run is True


def test_stop_disarms_the_button(button):
    calls: list = []
    _listen(button, "tick")
    button.worker(_context("start", calls))
    assert button.worker(_context("stop", calls)) == "stopped"

    button.button.run = True

    assert calls == []
    assert button.worker(_context("stop", calls)) is None  # already stopped


def test_restart_emits_on_the_new_context(button):
    old: list = []
    new: list = []
    _listen(button, "tick")
    button.worker(_context("start", old))
    button.on_shutdown(_context("", old))

    button.worker(_context("start", new))
    button.button.run = True

    assert len(new) == 1
    assert old == []


def test_starts_no_thread(button):
    before = set(threading.enumerate())
    button.worker(_context("start", []))
    assert set(threading.enumerate()) - before == set()
