"""Flow meters on the haystack row: the bar and strip, lazy tooltips, the row hook-up and the setting."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from haywire.core.access import AccessTier, access_resolver, set_access_resolver
from haywire.core.execution.flow_metrics import (
    FlowMeterSampler,
    FlowReading,
    FlowSnapshot,
    GroupReading,
    MeterReading,
    Severity,
)
from haywire.core.session.context import SessionContext
from haywire.core.undo.no_op_history_manager import NoOpHistoryManager
from haywire.ui.editor.wrapper import EditorWrapper
from nicegui import Client, ui

from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.state.graph_app_state import GraphAppState
from haybale_haystack.editors.haystack_editor import HaystackEditor
from haybale_haystack.flow_meter import FlowMeterView, bar_signature, describe, fill_step
from haybale_haystack.graph_entry import EntryKind
from haybale_haystack.state.haystack_state import HaystackState

pytestmark = pytest.mark.unit


def _flow(flow_id="f", group="g", severity=Severity.OK, load=0.0, **fields: Any) -> FlowReading:
    values: dict[str, Any] = {
        "flow_id": flow_id,
        "entry_node_id": f"node_{flow_id}",
        "group_id": group,
        "drop_mode": False,
        "load": load,
        "group_load": load,
        "fill": 0.0,
        "frame_rate": 10.0,
        "drop_rate": 0.0,
        "recently_dropped": False,
        "dropped_total": 0,
        "queue_depth": 0,
        "queue_max": 100,
        "severity": severity,
    }
    values.update(fields)
    return FlowReading(**values)


def _reading(*groups: list[FlowReading]) -> MeterReading:
    return MeterReading(
        tuple(GroupReading(g[0].group_id, 0.0, max(f.severity for f in g), tuple(g)) for g in groups)
    )


def _noop_page() -> None:
    pass


@pytest.fixture
def client():
    c = Client(cast(Any, _noop_page), request=None)
    with c:
        yield c


def _marked(client: Client, mark: str) -> list[Any]:
    return [el for el in client.elements.values() if el.props.get("data-hw-mark") == mark]


def _view(client: Client) -> FlowMeterView:
    with ui.row():
        view = FlowMeterView(lambda node_id: f"name of {node_id}")
        view.build()
    return view


def test_fill_step_rounds_to_ten_steps_and_clamps():
    assert [fill_step(x) for x in (-1, 0, 0.04, 0.05, 0.5, 0.96, 3)] == [0, 0, 0, 0, 5, 10, 10]


def test_a_bar_shows_the_larger_of_flow_and_runner_load():
    flow = _flow(load=0.1, group_load=0.8, severity=Severity.WARN)
    assert bar_signature(flow) == (Severity.WARN, 8)


def test_the_tooltip_describes_a_block_mode_flow():
    text = describe(
        _flow(queue_depth=40, queue_max=100, dropped_total=3, recently_dropped=True), "Audio Event"
    )
    assert "Audio Event (blocks when full)" in text
    assert "queue 40/100" in text
    assert "dropped 3 (just now)" in text


def test_the_tooltip_describes_a_drop_mode_flow():
    text = describe(_flow(drop_mode=True, drop_rate=0.25, dropped_total=7), "Camera")
    assert "Camera (drops by design)" in text
    assert "dropped 25% of triggers (7 in total)" in text


def test_the_collapsed_bar_follows_the_worst_flow_and_redraws_only_on_change(client):
    view = _view(client)
    (bar,) = _marked(client, "flow-meter")
    (fill,) = bar.default_slot.children[:1]
    view.update(_reading([_flow(severity=Severity.WARN, load=0.7)]))
    assert fill._style["height"] == "70%"
    assert fill._style["background"] == "var(--hw-warning)"

    client.outbox.updates.clear()
    view.update(_reading([_flow(severity=Severity.WARN, load=0.72)]))
    assert fill.id not in client.outbox.updates, "the same colour and step does not touch the element"

    view.update(_reading([_flow(severity=Severity.ALERT, load=0.95)]))
    assert fill._style["background"] == "var(--hw-danger)"
    assert fill.id in client.outbox.updates


def test_an_empty_reading_draws_an_empty_green_bar(client):
    view = _view(client)
    view.update(_reading([_flow(severity=Severity.ALERT, load=1.0)]))
    view.update(MeterReading(()))
    (bar,) = _marked(client, "flow-meter")
    assert bar.default_slot.children[0]._style["height"] == "0%"


def test_a_click_opens_the_strip_with_one_bar_per_flow_in_order(client):
    view = _view(client)
    view.update(
        _reading(
            [_flow("b1", "B", Severity.ALERT, 0.95), _flow("b2", "B", Severity.OK, 0.1)],
            [_flow("a1", "A", Severity.OK, 0.2)],
        )
    )
    assert _marked(client, "flow-bar") == [], "nothing is drawn while collapsed"
    view._toggle()
    bars = _marked(client, "flow-bar")
    assert len(bars) == 3
    colours = [b.default_slot.children[0]._style["background"] for b in bars]
    assert colours[0] == "var(--hw-danger)"
    assert bars[2]._style.get("margin-right") == "5px", "a gap separates the groups"
    assert "margin-right" not in bars[0]._style
    assert "margin-right" not in bars[1]._style
    view._toggle()
    assert view._strip is not None
    assert view._strip.visible is False


def test_the_open_strip_is_redrawn_only_when_something_changes(client):
    view = _view(client)
    view.update(_reading([_flow("a", load=0.5)]))
    view._toggle()
    (first,) = _marked(client, "flow-bar")
    view.update(_reading([_flow("a", load=0.52)]))
    assert _marked(client, "flow-bar") == [first], "the same step keeps the same elements"
    view.update(_reading([_flow("a", load=0.9, severity=Severity.ALERT)]))
    (second,) = _marked(client, "flow-bar")
    assert second is not first


def test_a_tooltip_is_written_when_it_opens_not_before(client):
    view = _view(client)
    view.update(_reading([_flow("a", load=0.5, queue_depth=3)]))
    view._toggle()
    tip = view._tips["a"]
    assert tip.text == ""
    view.update(_reading([_flow("a", load=0.5, queue_depth=9)]))
    assert tip.text == "", "a new reading sends no tooltip text"
    view._write_tip("a")
    assert "queue 9/100" in tip.text
    assert "name of node_a" in tip.text


# --- the row -------------------------------------------------------------------------------------


@dataclass
class _Editor:
    graph: object = None
    history_manager: Any = field(default_factory=NoOpHistoryManager)


class _Interpreter:
    def __init__(self) -> None:
        self.is_executing = True
        self.calls = 0

    def flow_metrics(self) -> list[FlowSnapshot]:
        self.calls += 1
        t = float(self.calls)
        return [
            FlowSnapshot("f1", "node_f1", "g", False, 0, 100, self.calls * 10, int(0.95e9 * t), 0, False, t),
        ]


@pytest.fixture(autouse=True)
def _restore_resolver():
    previous = access_resolver()
    yield
    set_access_resolver(previous)


def _row_editor(monkeypatch, *, executing: bool, enabled: bool = True):
    from nicegui import core

    monkeypatch.setattr(core, "loop", None)
    set_access_resolver(lambda name: AccessTier.ADMIN)
    interpreter = _Interpreter()
    node = SimpleNamespace(display_label="Block Ready")
    graph = SimpleNamespace(get_node_wrapper=lambda node_id: SimpleNamespace(node=node))
    entry = SimpleNamespace(
        binding_id="id",
        path=Path("/tmp/a.haywire"),
        unsaved=False,
        graph=graph,
        is_executing=executing,
        interpreter=interpreter if executing else None,
        kind=EntryKind.GRAPH,
        display_name="a",
    )
    hs = MagicMock()
    hs.entries_of_kind = MagicMock(side_effect=lambda kind: [entry] if kind.is_executable() else [])
    hs.get_by_id = MagicMock(return_value=entry)
    gas = GraphAppState()
    context = SessionContext(session_id="s1", app=MagicMock())
    context.principal = "someone"
    app_data = MagicMock()
    app_data.__getitem__.side_effect = lambda key: {HaystackState: hs, GraphAppState: gas}[key]
    context.app_data = app_data  # type: ignore[assignment]
    context.data[EditState].active_graph = None
    editor = HaystackEditor(cast(EditorWrapper, object()))
    monkeypatch.setattr(editor, "_flow_meters_enabled", lambda: enabled)
    return editor, context, interpreter


def _draw(editor: HaystackEditor, context: SessionContext) -> Client:
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        with ui.column():
            editor._list_container = ui.column()
            editor._meter_timer = ui.timer(0.5, lambda: None, active=False)
            editor._render_list(context)
    return client


def test_a_running_graph_row_gets_a_meter_and_starts_the_timer(monkeypatch):
    editor, context, _ = _row_editor(monkeypatch, executing=True)
    client = _draw(editor, context)
    assert len(_marked(client, "flow-meter")) == 1
    assert list(editor._meters) == ["id"]
    assert editor._meter_timer is not None
    assert editor._meter_timer.active is True


def test_a_stopped_graph_row_has_no_meter_and_the_timer_stays_off(monkeypatch):
    editor, context, _ = _row_editor(monkeypatch, executing=False)
    client = _draw(editor, context)
    assert _marked(client, "flow-meter") == []
    assert editor._meter_timer is not None
    assert editor._meter_timer.active is False


def test_the_setting_turns_the_meters_off(monkeypatch):
    editor, context, _ = _row_editor(monkeypatch, executing=True, enabled=False)
    client = _draw(editor, context)
    assert _marked(client, "flow-meter") == []
    assert editor._meter_timer is not None
    assert editor._meter_timer.active is False


def test_a_sample_updates_the_meter_from_the_interpreter(monkeypatch):
    editor, context, interpreter = _row_editor(monkeypatch, executing=True)
    client = _draw(editor, context)
    editor._sample_meters(context)  # primes the sampler
    editor._sample_meters(context)
    (bar,) = _marked(client, "flow-meter")
    fill = bar.default_slot.children[0]
    assert interpreter.calls == 2
    assert fill._style["background"] == "var(--hw-danger)", "a Flow busy 95% of the time is red"


def test_a_failing_sample_does_not_stop_the_timer(monkeypatch):
    editor, context, interpreter = _row_editor(monkeypatch, executing=True)
    _draw(editor, context)
    interpreter.flow_metrics = MagicMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]
    editor._sample_meters(context)


def test_the_flow_name_is_the_event_nodes_label_or_its_id(monkeypatch):
    editor, context, _ = _row_editor(monkeypatch, executing=True)
    entry = context.app_data[HaystackState].get_by_id("id")
    assert editor._flow_name(entry, "node_f1") == "Block Ready"
    entry.graph = SimpleNamespace(get_node_wrapper=lambda node_id: None)
    assert editor._flow_name(entry, "node_f1") == "node_f1"


def test_the_sampler_is_not_created_until_the_first_sample(monkeypatch):
    editor, context, _ = _row_editor(monkeypatch, executing=True)
    _draw(editor, context)
    assert editor._samplers == {}
    editor._sample_meters(context)
    assert isinstance(editor._samplers["id"], FlowMeterSampler)
