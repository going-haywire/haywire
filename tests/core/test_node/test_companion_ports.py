"""Companion ports: a port with an ``owner`` goes with that port, on every path that drops it."""

import pytest
from haybale_testing.types.test_types import TEST_STRING

from haywire.core.graph.base import BaseGraph
from haywire.core.node.promotion import remove_port
from haywire.core.types.enums import PortOrigin
from tests.core.test_types.test_add_type import _make_add_node, _make_link_node

pytestmark = pytest.mark.integration


def _validate(graph):
    graph._validation.force_immediate_validation()


@pytest.fixture
def grown(graph_with_library_system, library_system):
    """An Add Port TestNode whose ``str_in_0`` grew, with its note companion in a resolved fold."""
    graph = graph_with_library_system
    source = _make_link_node(graph, (0, 0))
    target = _make_add_node(graph, (300, 0))
    assert graph.create_edge_wrapper(source.node_id, "float_outlet", target.node_id, "str_in_0") is not None
    _validate(graph)
    return graph, source, target


def _notes_fold(node) -> str:
    return node._fold_id("Str 0 notes")


def test_a_grown_port_brings_its_companion_in_a_resolved_fold(grown):
    _, _, target = grown
    node = target.node
    note = node.ports["str_note_0"]
    assert note.owner == "str_in_0"
    assert note.origin is PortOrigin.RESOLVED
    assert note.parent_fold == _notes_fold(node)
    assert node.ports[_notes_fold(node)].origin is PortOrigin.RESOLVED


def test_a_companion_is_not_removable_on_its_own(grown):
    _, _, target = grown
    node = target.node
    assert node.ports["str_in_0"].is_user_removable()
    assert not node.ports["str_note_0"].is_user_removable()
    assert remove_port(node, "str_note_0") is False
    assert "str_note_0" in node.ports


def test_removing_the_owner_removes_its_companion_and_the_emptied_fold(grown):
    graph, source, target = grown
    node = target.node
    feed = graph.create_edge_wrapper(source.node_id, "float_outlet", target.node_id, "str_note_0")
    assert feed is not None

    assert remove_port(node, "str_in_0") is True
    assert "str_in_0" not in node.ports
    assert "str_note_0" not in node.ports
    assert _notes_fold(node) not in node.ports
    # Detached, not deleted: the edge waits for its port to come back.
    assert graph.get_edge_wrapper(feed.edge_id) is feed
    assert not feed.is_functional()


def test_an_author_rejig_dropping_the_owner_takes_its_companion(grown):
    _, _, target = grown
    node = target.node
    with node.rejig(include=["str_in_0"]):
        pass
    assert "str_note_0" not in node.ports


def test_re_adding_the_owner_in_the_same_rejig_keeps_its_companion(grown):
    _, _, target = grown
    node = target.node
    with node.rejig(include=["str_in_0"]):
        node._add_slot("str", 0, TEST_STRING, PortOrigin.RESOLVED)
    assert "str_note_0" in node.ports
    assert _notes_fold(node) in node.ports


def test_a_declared_fold_stays_when_its_companions_go(grown):
    _, _, target = grown
    node = target.node
    with node.fold("Extra"):
        node.add(TEST_STRING.as_inlet("extra_note", origin=PortOrigin.RESOLVED, owner="str_in_0"))
    fold_id = node._fold_id("Extra")

    assert remove_port(node, "str_in_0") is True
    assert "extra_note" not in node.ports
    assert fold_id in node.ports


def test_a_companion_of_a_companion_goes_too(grown):
    _, _, target = grown
    node = target.node
    node.add(TEST_STRING.as_inlet("deep_note", origin=PortOrigin.RESOLVED, owner="str_note_0"))
    assert remove_port(node, "str_in_0") is True
    assert "deep_note" not in node.ports


def _reload(graph) -> BaseGraph:
    loaded = BaseGraph(filestem="reloaded")
    assert loaded.load_from_dict(graph.to_dict()) is True
    _validate(loaded)
    return loaded


def _find_port(tree, port_id: str) -> dict:
    """The saved spec of *port_id* anywhere under *tree*."""
    if isinstance(tree, dict):
        ports = tree.get("ports")
        if isinstance(ports, dict) and port_id in ports:
            return ports[port_id]
        for value in tree.values():
            found = _find_port(value, port_id)
            if found:
                return found
    return {}


def test_the_owner_survives_save_and_load(grown):
    graph, _, target = grown
    loaded = _reload(graph).get_node_wrapper(target.node_id)
    note = loaded.node.ports["str_note_0"]
    assert note.owner == "str_in_0"
    assert not note.is_user_removable()
    assert remove_port(loaded.node, "str_in_0") is True
    assert "str_note_0" not in loaded.node.ports


def test_a_saved_port_without_an_owner_loads_as_its_own(grown):
    graph, _, target = grown
    data = graph.to_dict()
    saved = _find_port(data["nodes"][target.node_id], "str_note_0")
    del saved["kwargs"]["owner"]

    loaded = BaseGraph(filestem="reloaded")
    assert loaded.load_from_dict(data) is True
    note = loaded.get_node_wrapper(target.node_id).node.ports["str_note_0"]
    assert note.owner is None
    assert note.is_user_removable()
