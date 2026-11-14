"""``on_pin_removed`` and ``on_pin_restored``: a pin removal reaches its node through the undo step."""

import pytest
from haybale_testing.types.test_types import TEST_STRING

from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.graph.editor import Editor
from haywire.core.node.promotion import remove_port
from tests.core.test_types.test_add_type import _make_add_node, _make_link_node

pytestmark = pytest.mark.integration


def _validate(graph):
    graph._validation.force_immediate_validation()


@pytest.fixture
def ledger():
    previous = get_error_ledger()
    fresh = ErrorLedger(max_entries=20)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(previous)


@pytest.fixture
def setup(graph_with_library_system, library_system):
    """An Add Port TestNode with two grown ``Str`` pins, each fed, and the first one's note fed too."""
    graph = graph_with_library_system
    source = _make_link_node(graph, (0, 0))
    target = _make_add_node(graph, (300, 0))
    editor = Editor(graph, source._node_factory)
    feeds = [
        graph.create_edge_wrapper(source.node_id, "float_outlet", target.node_id, port_id)
        for port_id in ("str_in_0", "str_in_1", "str_note_0")
    ]
    _validate(graph)
    assert all(edge is not None and edge.is_functional() for edge in feeds)
    editor.history_manager.add_fence()
    return graph, editor, target.node, feeds


def _hook_entries(ledger) -> list:
    """The ledger's ``Remove pin`` entries; a detached edge's validation records its own."""
    return [entry for entry in ledger.query().entries if entry.operation == "Remove pin"]


def _grown(node) -> list[str]:
    return list(node.store.str_grown)


def test_removal_tells_the_node_and_undo_and_redo_reverse_it(setup):
    graph, editor, node, (first, _, note_feed) = setup
    orders = {pid: node.ports[pid].order for pid in ("str_in_0", "str_note_0", node._fold_id("Str 0 notes"))}
    assert _grown(node) == ["str_in_0", "str_in_1"]

    assert editor.remove_port(node.node_id, "str_in_0")
    _validate(graph)
    assert _grown(node) == ["str_in_1"]
    assert "str_note_0" not in node.ports

    assert editor.undo()
    _validate(graph)
    assert _grown(node) == ["str_in_0", "str_in_1"]
    assert {pid: node.ports[pid].order for pid in orders} == orders
    assert node.ports["str_note_0"].owner == "str_in_0"
    assert first.is_functional()
    assert note_feed.is_functional()

    assert editor.redo()
    _validate(graph)
    assert _grown(node) == ["str_in_1"]
    assert editor.undo()
    assert _grown(node) == ["str_in_0", "str_in_1"]


def test_each_redo_hands_undo_a_fresh_memento(setup):
    graph, editor, node, _ = setup
    assert editor.remove_port(node.node_id, "str_in_1")
    assert editor.undo()
    # Between the undo and the redo the node's list changes shape; the redo's memento must follow it.
    node.store.str_grown = ["str_in_x", *_grown(node)]
    assert editor.redo()
    assert _grown(node) == ["str_in_x", "str_in_0"]
    assert editor.undo()
    assert _grown(node) == ["str_in_x", "str_in_0", "str_in_1"]


def test_a_bare_remove_port_does_not_call_the_hook(setup):
    _, _, node, _ = setup
    assert remove_port(node, "str_in_0") is True
    assert _grown(node) == ["str_in_0", "str_in_1"]


def test_a_companion_is_refused_by_the_action(setup):
    _, editor, node, _ = setup
    assert editor.remove_port(node.node_id, "str_note_0") is False
    assert "str_note_0" in node.ports


def test_a_hook_changing_ports_is_recorded_and_the_step_stays_whole(setup, ledger, monkeypatch):
    graph, editor, node, (first, _, _) = setup

    def grows_a_port(port_id, spec):
        node.add(TEST_STRING.as_inlet("sneaky"))

    monkeypatch.setattr(node, "on_pin_removed", grows_a_port)
    assert editor.remove_port(node.node_id, "str_in_0")
    (entry,) = _hook_entries(ledger)
    assert entry.node_id == node.node_id
    assert entry.details["hook"] == "on_pin_removed"
    assert entry.details["ports"] == ["sneaky"]

    assert editor.undo()
    _validate(graph)
    assert first.is_functional()


@pytest.mark.parametrize("failing", ["on_pin_removed", "on_pin_restored"])
def test_a_raising_hook_is_recorded_and_the_step_stays_undoable(setup, ledger, monkeypatch, failing):
    graph, editor, node, (first, _, _) = setup
    restored: list = []

    def boom(*args):
        raise KeyError("boom")

    monkeypatch.setattr(node, failing, boom)
    if failing == "on_pin_removed":
        monkeypatch.setattr(node, "on_pin_restored", lambda port_id, memento: restored.append(memento))

    assert editor.remove_port(node.node_id, "str_in_0")
    assert "str_in_0" not in node.ports
    assert editor.undo()
    _validate(graph)
    assert "str_note_0" in node.ports
    assert first.is_functional()

    (entry,) = _hook_entries(ledger)
    assert entry.details["hook"] == failing
    if failing == "on_pin_removed":
        assert restored == [None]
