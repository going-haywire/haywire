"""Run Button: a press on its button triggers its listeners once, while the graph runs."""

from __future__ import annotations

import threading
import time
from functools import partial
from types import SimpleNamespace
from typing import Any

import pytest

from haywire.barn.builtin.widget_keys import BUTTON_WIDGET
from haywire.core.graph.base import BaseGraph
from haywire.core.types.enums import PortType
from tests.conftest import make_node
from tests.wait import wait_until

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
    """A context whose ``emit_callback`` records one ``(names, payload, backlog)`` per emit."""
    return SimpleNamespace(
        control_pin=control_pin,
        emit_callback=lambda event_name, payload=None, backlog=None: calls.append(
            (event_name, payload, backlog)
        ),
    )


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

    # One emit carries every name, so pooled Tick Events share the press (ADR 0097).
    assert calls == [(["tick_a", "tick_b"], {"delta_time": 0.0}, button.backlog)]
    assert wait_until(lambda: button.button.run is False)
    assert len(calls) == 1


def test_second_press_reports_time_since_previous(button):
    calls: list = []
    _listen(button, "tick")
    button.worker(_context("start", calls))

    button.button.run = True
    assert wait_until(lambda: button.button.run is False)
    time.sleep(0.06)  # the gap the second press reports; a sleep never ends early
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

    # A press while stopped returns from the setter's handler before it emits or posts anything.
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


def _ran(runs: list[str], count: int) -> bool:
    return len(runs) == count


def test_pooled_tick_events_take_one_press_each(graph_with_library_system):
    from haybale_core.nodes.events.tick_event import TickEventNode
    from haywire.core.execution.interpreter import Interpreter

    button = _button(graph_with_library_system)
    key = TickEventNode.class_identity.registry_key
    ticks: list[Any] = [
        make_node(graph_with_library_system, key, position=(0, 200 * i)).node for i in range(2)
    ]
    runs: list[str] = []
    release = threading.Event()
    for tick in ticks:
        tick.delivery.mode = "Pooled"

        def worker(context: Any, node: Any = tick) -> str:
            runs.append(node.node_id)
            release.wait(timeout=5.0)  # holds the member busy until both presses are in
            return "exec"

        tick.worker = worker
    _listen(button, *(tick.node_id for tick in ticks))

    interpreter = Interpreter()
    interpreter.load_graph(graph_with_library_system)
    interpreter.start_execution()
    try:
        button.worker(SimpleNamespace(control_pin="start", emit_callback=interpreter.vm.emit_callback))
        for presses in (1, 2):
            button.button.run = True
            assert wait_until(partial(_ran, runs, presses)), "the press reaches a free Tick Event"
            assert wait_until(lambda: button.button.run is False)
        release.set()
        interpreter.wait_all(timeout=10.0)
    finally:
        release.set()
        button.on_teardown()
        interpreter.shutdown()

    assert sorted(runs) == sorted(tick.node_id for tick in ticks), "each Tick Event takes one press"
