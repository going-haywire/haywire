"""The run policy on_exception_bail reaches the VM; bail 'run' stops the entry outside the runner thread."""

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


def test_the_policy_defaults_to_branch_and_offers_three_scopes():
    from haybale_haystack.settings.graph_run_settings import GraphRunSettings

    settings = GraphRunSettings()

    assert settings.on_exception_bail == "branch"
    options = GraphRunSettings.on_exception_bail.widget_config["properties"]["options"]
    assert set(options) == {"run", "frame", "branch"}


def test_compile_hands_the_live_policy_and_the_stop_request_to_the_vm(monkeypatch):
    from haybale_haystack import graph_entry as graph_entry_mod
    from haybale_haystack.graph_entry import GraphEntry

    built: dict = {}

    class _FakeInterpreter:
        def __init__(self, **kwargs):
            built.update(kwargs)

        def load_graph(self, graph):
            pass

    monkeypatch.setattr(graph_entry_mod, "Interpreter", _FakeInterpreter)
    monkeypatch.setattr(graph_entry_mod, "get_library_state_container", lambda: None)
    graph = MagicMock()
    entry = GraphEntry(graph=graph, editor=MagicMock())
    monkeypatch.setattr(GraphEntry, "is_executing", property(lambda self: False))

    assert entry.compile().ok

    entry.run_settings.on_exception_bail = "frame"
    assert built["exception_bail"]() == "frame"  # read live, not captured at compile

    stop = MagicMock()
    monkeypatch.setattr(entry, "stop_execution", stop)
    built["on_bail_run"]()
    graph._validation.call_soon.assert_called_once()
    (scheduled,), _ = graph._validation.call_soon.call_args
    stop.assert_not_called()  # never on the runner thread
    scheduled()
    stop.assert_called_once()  # no haystack: the entry stops itself


def test_bail_run_stops_through_the_haystack_and_tells_the_ui(monkeypatch):
    from haybale_haystack import graph_entry as graph_entry_mod
    from haybale_haystack.graph_entry import GraphEntry

    built: dict = {}

    class _FakeInterpreter:
        def __init__(self, **kwargs):
            built.update(kwargs)

        def load_graph(self, graph):
            pass

    monkeypatch.setattr(graph_entry_mod, "Interpreter", _FakeInterpreter)
    monkeypatch.setattr(graph_entry_mod, "get_library_state_container", lambda: None)
    graph = MagicMock()
    graph._validation.call_soon.side_effect = lambda fn: fn()
    haystack = MagicMock()
    entry = GraphEntry(graph=graph, editor=MagicMock(), haystack=haystack)
    monkeypatch.setattr(GraphEntry, "is_executing", property(lambda self: False))
    entry.compile()

    built["on_bail_run"]()

    haystack.stop_execution.assert_called_once_with(entry)
    haystack._broadcast_data_mutated.assert_called_once_with()
