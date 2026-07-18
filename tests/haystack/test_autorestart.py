"""Autorestart after a reassembly-requiring validation stop."""

from unittest.mock import MagicMock


def _reassembly_result():
    """A ValidationResult-like double whose graph-change reason requires reassembly."""
    result = MagicMock()
    result.has_changes.return_value = True
    result.nodes = {}
    result.edges = {}
    reason = MagicMock()
    reason.requires_graph_reassembly.return_value = True
    result.graph = reason
    return result


def _make_state():
    from haybale_haystack.state.haystack_state import HaystackState

    # __init__ may require deps; construct via object.__new__ and only
    # exercise _on_entry_validation, which is self-contained.
    state = object.__new__(HaystackState)
    state._broadcast_data_mutated = MagicMock()
    return state


def test_autorestart_off_only_stops(monkeypatch):
    from haybale_haystack.graph_entry import GraphEntry
    from haywire.core.execution.compile_result import CompileResult

    entry = GraphEntry(graph=MagicMock(), editor=MagicMock())
    entry.run_settings.autorestart = False

    running = MagicMock()
    running.is_executing = True
    entry.interpreter = running

    calls = []
    monkeypatch.setattr(entry, "stop_execution", lambda: calls.append("stop"))
    monkeypatch.setattr(entry, "start_execution", lambda: (calls.append("start"), CompileResult(ok=True))[1])

    state = _make_state()
    state._on_entry_validation(entry, _reassembly_result())

    assert calls == ["stop"]


def test_autorestart_on_restarts_when_compile_ok(monkeypatch):
    from haybale_haystack.graph_entry import GraphEntry
    from haywire.core.execution.compile_result import CompileResult

    entry = GraphEntry(graph=MagicMock(), editor=MagicMock())
    entry.run_settings.autorestart = True

    running = MagicMock()
    running.is_executing = True
    entry.interpreter = running

    calls = []
    monkeypatch.setattr(entry, "stop_execution", lambda: calls.append("stop"))
    monkeypatch.setattr(entry, "start_execution", lambda: (calls.append("start"), CompileResult(ok=True))[1])

    state = _make_state()
    state._on_entry_validation(entry, _reassembly_result())

    assert calls == ["stop", "start"]


def test_autorestart_on_stays_stopped_when_compile_fails(monkeypatch):
    from haybale_haystack.graph_entry import GraphEntry
    from haywire.core.execution.compile_result import CompileResult

    entry = GraphEntry(graph=MagicMock(), editor=MagicMock())
    entry.run_settings.autorestart = True

    running = MagicMock()
    running.is_executing = True
    entry.interpreter = running

    calls = []
    monkeypatch.setattr(entry, "stop_execution", lambda: calls.append("stop"))
    monkeypatch.setattr(
        entry,
        "start_execution",
        lambda: (calls.append("start"), CompileResult(ok=False, error="bad"))[1],
    )

    state = _make_state()
    state._on_entry_validation(entry, _reassembly_result())

    # restart was attempted (start called) but it failed — entry stays stopped,
    # no crash. The attempt is expected; the assertion is that it didn't raise
    # and stop happened first.
    assert calls[0] == "stop"
    assert "start" in calls
