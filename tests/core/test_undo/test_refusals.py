"""An edit a correct program can attempt is refused, unrecorded; one only a bug can reach is recorded.

Each refusal kind goes through the ``Editor`` path that reports to the error ledger
(an unrecorded write), so a refusal still raised as a ``ValueError`` would show up there.
"""

import pytest

from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.graph.editor import Editor
from haywire.core.graph.setting_owner import SettingOwner
from haywire.core.types import Propagation
from haywire.core.types.enums import PortType
from haywire.core.undo.actions.graph_actions import (
    AddEdgeAction,
    PromoteSettingAction,
    SetEdgePropagationAction,
    _RestoreSubgraphAction,
)
from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


@pytest.fixture
def ledger():
    previous = get_error_ledger()
    fresh = ErrorLedger(max_entries=5)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(previous)


@pytest.fixture
def editor(graph_with_library_system, library_system):
    return Editor(graph_with_library_system, library_system.get_node_factory())


@pytest.fixture
def add_key():
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    return TestAddFloatNode.class_identity.registry_key


def test_a_stale_node_is_refused(ledger, editor):
    owner = SettingOwner(kind="node", accessor="props", owner_id="removed_elsewhere")

    assert editor.set_setting(owner, "label", "x", record=False) is False
    assert ledger.query().total == 0


def test_an_unknown_setting_name_is_refused(ledger, editor, add_key):
    node = make_node(editor.graph, add_key)
    ledger.clear()
    owner = SettingOwner(kind="node", accessor="props", owner_id=node.node_id)

    assert editor.set_setting(owner, "no_such_field", 1, record=False) is False
    assert ledger.query().total == 0


def test_a_stale_edge_is_refused(ledger, editor):
    action = SetEdgePropagationAction(editor.graph, "removed_elsewhere", Propagation.LAZY)

    assert editor._apply(action, record=False) is False
    assert ledger.query().total == 0


def test_an_edge_between_already_linked_pins_is_refused(ledger, editor, add_key):
    a = make_node(editor.graph, add_key)
    b = make_node(editor.graph, add_key)
    make_edge(editor.graph, a.node_id, "result", b.node_id, "value_a")
    ledger.clear()
    action = AddEdgeAction(
        graph=editor.graph,
        source_node_id=a.node_id,
        outlet_pin_id="result",
        sink_node_id=b.node_id,
        inlet_pin_id="value_a",
    )

    assert editor._apply(action, record=False) is False
    assert ledger.query().total == 0


def test_an_ineligible_promotion_is_refused(ledger, editor, add_key):
    node = make_node(editor.graph, add_key)
    ledger.clear()
    action = PromoteSettingAction(editor.graph, node.node_id, "props", "label", PortType.SWINGLET)

    assert editor._apply(action, record=False) is False
    assert ledger.query().total == 0


def test_a_broken_invariant_is_recorded(ledger, editor):
    from haywire.core.graph.subgraph import SubgraphDefinition

    editor.graph.add_subgraph(SubgraphDefinition(key="taken"))
    ledger.clear()
    # A Subgraph key is minted unique, so restoring onto a taken one is a bug.
    action = _RestoreSubgraphAction(editor.graph, "taken", {"label": "taken"})

    assert editor._apply(action, record=False) is False
    (entry,) = ledger.query().entries
    assert entry.operation == "Apply edit"
