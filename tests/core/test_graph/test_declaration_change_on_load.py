"""Loading a graph whose file was saved against another declaration of a node's class."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.undo.config import UndoConfig

from tests.conftest import make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"


@pytest.fixture
def ledger():
    previous = get_error_ledger()
    fresh = ErrorLedger(max_entries=20)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(previous)


def _graph(name: str = "g") -> BaseGraph:
    return BaseGraph(filestem=name, validation_scheduler=SyncScheduler())


def _saved_with_a_set_value() -> tuple[dict[str, Any], str]:
    """Return a saved one-node graph whose node has a value, a label and a position, and the node's id."""
    graph = _graph()
    wrapper = make_node(graph, _ADD, position=(120, 80))
    wrapper.node.ports["value_a"].set_value(4.5)
    wrapper.node.props.label = "Mine"
    return graph.to_dict(), wrapper.node_id


def _as_saved_against_other_code(saved: dict[str, Any]) -> dict[str, Any]:
    """Return *saved* as a file written when the class also declared a port ``gone``."""
    older = copy.deepcopy(saved)
    declaration = older["declarations"][_ADD]
    declaration["gone"] = copy.deepcopy(declaration["value_a"])
    declaration["gone"]["kwargs"]["id"] = "gone"
    return older


def _loaded(saved: dict[str, Any], node_id: str) -> tuple[BaseGraph, Any]:
    graph = _graph("loaded")
    assert graph.load_from_dict(saved) is True
    return graph, graph.node_wrappers[node_id]


def test_an_unchanged_declaration_loads_the_node_from_its_file(library_system, ledger):
    saved, node_id = _saved_with_a_set_value()

    _graph_, wrapper = _loaded(saved, node_id)

    assert wrapper.node.ports["value_a"].get_value() == 4.5
    assert wrapper.previous_setup is None
    assert ledger.query().total == 0


def test_a_changed_declaration_resets_the_node_and_keeps_its_setup(library_system, ledger):
    saved, node_id = _saved_with_a_set_value()
    older = _as_saved_against_other_code(saved)

    _graph_, wrapper = _loaded(older, node_id)

    assert wrapper.node.ports["value_a"].get_value() != 4.5
    assert wrapper.node.props.label != "Mine"
    held = wrapper.previous_setup
    assert held is not None
    assert held["ports"]["value_a"]["field_data"] == {"value": 4.5}
    assert held["declared"] == older["declarations"][_ADD]
    assert [w.kind for w in wrapper.state.warnings] == ["previous_setup"]
    (entry,) = ledger.query().entries
    assert (entry.operation, entry.node_id) == ("Load graph", node_id)


def test_a_reset_node_stays_where_the_file_put_it(library_system):
    saved, node_id = _saved_with_a_set_value()

    _graph_, wrapper = _loaded(_as_saved_against_other_code(saved), node_id)

    assert wrapper.node.props.get_position() == (120.0, 80.0)


def test_an_untouched_node_of_a_changed_class_keeps_nothing(library_system, ledger):
    graph = _graph()
    wrapper = make_node(graph, _ADD, position=(120, 80))
    older = _as_saved_against_other_code(graph.to_dict())

    _graph_, loaded = _loaded(older, wrapper.node_id)

    assert loaded.previous_setup is None
    assert ledger.query().total == 0


def test_a_file_without_a_declaration_for_the_class_loads_unchecked(library_system):
    saved, node_id = _saved_with_a_set_value()
    del saved["declarations"][_ADD]

    _graph_, wrapper = _loaded(saved, node_id)

    assert wrapper.node.ports["value_a"].get_value() == 4.5
    assert wrapper.previous_setup is None


def test_a_reset_node_saves_against_the_current_declaration(library_system):
    saved, node_id = _saved_with_a_set_value()
    graph, wrapper = _loaded(_as_saved_against_other_code(saved), node_id)

    again = graph.to_dict()

    assert again["declarations"][_ADD] == saved["declarations"][_ADD]
    reopened, same = _loaded(again, node_id)
    assert same.previous_setup == wrapper.previous_setup
    assert same.node.ports["value_a"].get_value() != 4.5


def test_restore_puts_the_setup_on_the_ports_the_code_declares_now(library_system):
    saved, node_id = _saved_with_a_set_value()
    older = _as_saved_against_other_code(saved)
    # The older file also holds the port the class has since dropped.
    node_ports = older["nodes"][node_id]["node_data"]["ports"]
    node_ports["gone"] = {
        "recipe": node_ports["value_a"]["recipe"],
        "kwargs": {"id": "gone", "port_type": "inlet"},
    }
    graph, wrapper = _loaded(older, node_id)
    editor = Editor(
        graph, library_system.get_node_factory(), undo_config=UndoConfig(enable_auto_grouping=False)
    )

    assert editor.apply_previous_setup([node_id]) is True
    graph._validation.force_immediate_validation()

    assert wrapper.node.ports["value_a"].get_value() == 4.5
    assert wrapper.node.props.label == "Mine"
    assert "gone" not in wrapper.node.ports
    assert wrapper.previous_setup is None


def test_restore_keeps_a_port_the_user_grew(library_system):
    from haywire.barn.builtin.types import FLOAT

    graph = _graph()
    source = make_node(graph, _ADD)
    source.node.add(FLOAT.as_inlet("grown", label="Grown"))
    older = _as_saved_against_other_code(graph.to_dict())
    loaded_graph, wrapper = _loaded(older, source.node_id)
    assert "grown" not in wrapper.node.ports
    editor = Editor(
        loaded_graph, library_system.get_node_factory(), undo_config=UndoConfig(enable_auto_grouping=False)
    )

    assert editor.apply_previous_setup([source.node_id]) is True
    loaded_graph._validation.force_immediate_validation()

    assert wrapper.node.ports["grown"].label == "Grown"


# ---------------------------------------------------------------------------
# A node whose init() declares something of its own
# ---------------------------------------------------------------------------

#: Its ``init()`` uses the node's id as the default of an outlet.
_OWN = "haybale-testing:node:TestRecordEventNode"


def test_two_nodes_that_declare_their_own_default_load_unchanged(library_system, ledger):
    graph = _graph()
    first, second = make_node(graph, _OWN), make_node(graph, _OWN)
    assert first.node.saved_declaration != second.node.saved_declaration
    first.node.props.label = "First"
    second.node.props.label = "Second"

    saved = graph.to_dict()
    loaded = _graph("loaded")
    assert loaded.load_from_dict(saved) is True

    for wrapper in (first, second):
        same = loaded.node_wrappers[wrapper.node_id]
        assert same.previous_setup is None
        assert same.node.props.label == wrapper.node.props.label
    assert ledger.query().total == 0


def test_only_a_node_that_differs_from_its_class_entry_carries_its_declaration(library_system):
    graph = _graph()
    first, second = make_node(graph, _OWN), make_node(graph, _OWN)
    plain = make_node(graph, _ADD)

    nodes = graph.to_dict()["nodes"]

    carrying = [node_id for node_id, node in nodes.items() if "declared" in node["node_data"]]
    assert len(carrying) == 1
    assert carrying[0] in (first.node_id, second.node_id)
    assert "declared" not in nodes[plain.node_id]["node_data"]


def test_a_nodes_own_declaration_is_checked_like_the_class_entry(library_system):
    graph = _graph()
    first, second = make_node(graph, _OWN), make_node(graph, _OWN)
    for wrapper in (first, second):
        wrapper.node.props.label = "Mine"
    saved = graph.to_dict()
    (carrier,) = [n for n in saved["nodes"].values() if "declared" in n["node_data"]]
    carrier["node_data"]["declared"]["gone"] = {"recipe": {"registry_key": "none"}, "kwargs": {}}

    loaded = _graph("loaded")
    assert loaded.load_from_dict(saved) is True

    assert loaded.node_wrappers[carrier["node_id"]].previous_setup is not None


def test_an_event_node_that_publishes_its_id_declares_the_same_as_its_class(library_system):
    graph = _graph()
    first, second = (
        make_node(graph, "haybale-core:node:TickEventNode"),
        make_node(graph, "haybale-core:node:TickEventNode"),
    )

    saved = graph.to_dict()

    assert first.node.saved_declaration == second.node.saved_declaration
    assert all("declared" not in node["node_data"] for node in saved["nodes"].values())
    loaded = _graph("loaded")
    assert loaded.load_from_dict(saved) is True
    for wrapper in (first, second):
        assert (
            loaded.node_wrappers[wrapper.node_id].node.ports["listen_callback"].get_value()
            == wrapper.node_id
        )
