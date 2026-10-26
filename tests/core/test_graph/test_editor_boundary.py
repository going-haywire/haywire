"""A failing Editor write reaches the error ledger and returns ``False``; a refusal does not."""

import pytest

from haywire.core.errors import Refusal
from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.graph.editor import Editor
from haywire.core.undo.interfaces import IAction

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


class _Raising(IAction):
    """An action whose ``execute`` raises *error*; ``changed`` lets it pass as a value write."""

    changed = True

    def __init__(self, error: Exception, node_id: str | None = None):
        self._error = error
        if node_id is not None:
            self.node_id = node_id

    @property
    def description(self) -> str:
        return "Raising"

    def execute(self) -> None:
        raise self._error

    def undo(self) -> None: ...

    def redo(self) -> None: ...


def test_a_failing_action_is_recorded_and_returns_false(ledger, editor):
    action = _Raising(KeyError("gone"), node_id="n1")

    assert editor._apply(action, record=False) is False

    (entry,) = ledger.query().entries
    assert entry.operation == "Apply edit"
    assert entry.graph_id == editor.graph.graph_id
    assert entry.node_id == "n1"
    assert entry.error_context["action"] == "Raising"


def test_a_refusing_action_returns_false_unrecorded(ledger, editor):
    assert editor._apply(_Raising(Refusal("stale")), record=False) is False
    assert ledger.query().total == 0


def test_a_failing_value_write_is_recorded(ledger, editor):
    assert editor._apply_value(_Raising(RuntimeError("boom")), record=False, merge_owner=None) is False

    (entry,) = ledger.query().entries
    assert entry.operation == "Apply edit"
    assert entry.node_id is None


def test_a_refusing_value_write_is_unrecorded(ledger, editor):
    assert editor._apply_value(_Raising(Refusal("stale")), record=False, merge_owner=None) is False
    assert ledger.query().total == 0


def test_a_failing_reset_is_recorded(ledger, editor, monkeypatch):
    from haywire.core.undo.actions import graph_actions
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode
    from tests.conftest import make_node

    node = make_node(editor.graph, TestAddFloatNode.class_identity.registry_key)
    assert isinstance(node.node, TestAddFloatNode)
    ledger.clear()

    def broken(*args, **kwargs):
        raise KeyError("capture")

    monkeypatch.setattr(graph_actions.RebuildNodesAction, "capture", broken)

    assert editor.reset_nodes([node.node_id]) is False

    (entry,) = ledger.query().entries
    assert entry.operation == "Reset nodes"
    assert entry.error_context["node_ids"] == [node.node_id]
