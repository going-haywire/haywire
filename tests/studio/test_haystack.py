"""Unit tests for Haystack entry lifecycle + validation wiring."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import haywire.core.graph.editor  # noqa: F401 -- circular-import guard

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire_studio.haystack import GraphEntry, Haystack


def _fake_factory():
    def _factory(graph_id: str, name: str):
        graph = BaseGraph(graph_id, name)
        editor = Editor(graph, node_factory=MagicMock(), undo_config=MagicMock())
        return graph, editor

    return _factory


def _make_haystack(tmp_path: Path, session_manager=None):
    return Haystack(
        workspace_root=tmp_path,
        graph_factory=_fake_factory(),
        session_manager=session_manager or MagicMock(),
    )


# --- create_new / open_graph ------------------------------------------------


def test_create_new_returns_entry(tmp_path: Path) -> None:
    haystack = _make_haystack(tmp_path)

    entry = haystack.create_new()

    assert isinstance(entry, GraphEntry)
    assert entry.path is None


def test_create_new_keys_each_entry_uniquely(tmp_path: Path) -> None:
    haystack = _make_haystack(tmp_path)

    a = haystack.create_new()
    b = haystack.create_new()

    assert a is not b
    assert a.graph.graph_id != b.graph.graph_id
    entries = haystack.all_entries()
    assert "__unsaved_1__" in entries
    assert "__unsaved_2__" in entries
    assert entries["__unsaved_1__"] is a
    assert entries["__unsaved_2__"] is b


def test_open_graph_reuses_entry_for_same_path(tmp_path: Path) -> None:
    path = tmp_path / "g.haywire"
    # Seed a valid graph file via BaseGraph.save_to_file
    seed = BaseGraph("seed", "seed")
    assert seed.save_to_file(str(path)) is True

    haystack = _make_haystack(tmp_path)

    first = haystack.open_graph(path)
    second = haystack.open_graph(path)

    assert first is second


# --- validation wiring ------------------------------------------------------


def test_new_entry_subscribes_validation_callback(tmp_path: Path) -> None:
    """Creating an entry wires its graph to Haystack._on_entry_validation."""
    haystack = _make_haystack(tmp_path)
    entry = haystack.create_new()

    sm = haystack._session_manager
    result = MagicMock()
    result.nodes = [object()]  # truthy -> data-mutating
    result.edges = []
    result.has_changes.return_value = True
    result.graph = None

    haystack._on_entry_validation(entry, result)

    assert entry.unsaved is True
    sm.broadcast_signal.assert_called_once()
    # Confirm the broadcast carries the new GraphDataMutated signal type.
    from haywire.core.session.context_signals import GraphDataMutated

    args, kwargs = sm.broadcast_signal.call_args
    assert isinstance(args[0], GraphDataMutated)


def test_on_entry_validation_stops_execution_on_reassembly(tmp_path: Path) -> None:
    haystack = _make_haystack(tmp_path)

    # Use a stand-in entry so the class-level `is_executing` property on
    # GraphEntry isn't mutated for subsequent tests.
    entry = MagicMock()
    entry.is_executing = True
    entry.stop_execution = MagicMock()

    inner_graph = MagicMock()
    inner_graph.requires_graph_reassembly.return_value = True

    result = MagicMock()
    result.nodes = []
    result.edges = []
    result.has_changes.return_value = True
    result.graph = inner_graph

    haystack._on_entry_validation(entry, result)

    entry.stop_execution.assert_called_once()


def test_on_entry_validation_non_mutating_does_not_broadcast(tmp_path: Path) -> None:
    haystack = _make_haystack(tmp_path)
    entry = haystack.create_new()
    sm = haystack._session_manager
    sm.broadcast.reset_mock()

    result = MagicMock()
    result.nodes = []
    result.edges = []
    result.has_changes.return_value = False
    result.graph = None

    haystack._on_entry_validation(entry, result)

    assert entry.unsaved is False
    sm.broadcast.assert_not_called()


# --- removed signatures -----------------------------------------------------


def test_graph_entry_has_no_sessions_field(tmp_path: Path) -> None:
    """entry.sessions was deleted; accessing it should raise."""
    haystack = _make_haystack(tmp_path)
    entry = haystack.create_new()

    with pytest.raises(AttributeError):
        _ = entry.sessions


def test_haystack_has_no_session_attach(tmp_path: Path) -> None:
    haystack = _make_haystack(tmp_path)
    assert not hasattr(haystack, "session_attach")
    assert not hasattr(haystack, "session_detach")
    assert not hasattr(haystack, "sessions_for_entry")
