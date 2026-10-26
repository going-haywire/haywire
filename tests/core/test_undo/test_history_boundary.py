"""``HistoryManager`` records a failing edit, undo or redo in the error ledger once; a refusal not at all."""

import pytest

from haywire.core.errors import Refusal
from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.graph.editor import Editor
from haywire.core.types import Propagation
from haywire.core.undo.base_action import ActionBase

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


class _Flaky(ActionBase):
    """An action whose execute, undo or redo raises *error* once ``fail`` names that phase."""

    changed = True

    def __init__(self, error: Exception, fail: str):
        super().__init__("Flaky")
        self._error = error
        self.fail = fail
        self._runs = 0

    def _execute_impl(self) -> None:
        self._runs += 1
        if self.fail == "execute" or (self.fail == "redo" and self._runs > 1):
            raise self._error

    def _undo_impl(self) -> None:
        if self.fail == "undo":
            raise self._error


def test_a_recorded_edit_that_fails_is_recorded_once(ledger, editor):
    assert editor._apply(_Flaky(KeyError("gone"), "execute"), record=True) is False

    (entry,) = ledger.query().entries
    assert entry.operation == "Apply edit"
    assert entry.error_context["action"] == "Flaky"


def test_a_recorded_edit_that_refuses_is_not_recorded(ledger, editor):
    assert editor.set_edge_propagation("removed_elsewhere", Propagation.LAZY) is False
    assert ledger.query().total == 0


def test_a_failing_value_write_on_the_recorded_path_is_recorded(ledger, editor):
    action = _Flaky(RuntimeError("boom"), "execute")

    assert editor._apply_value(action, record=True, merge_owner=None) is False

    (entry,) = ledger.query().entries
    assert entry.operation == "Apply edit"


def test_an_undo_that_fails_is_recorded(ledger, editor):
    assert editor._apply(_Flaky(KeyError("gone"), "undo"), record=True) is True

    assert editor.history_manager.undo() is False

    (entry,) = ledger.query().entries
    assert entry.operation == "Undo"
    assert entry.error_context["action"]


def test_a_redo_that_fails_is_recorded(ledger, editor):
    assert editor._apply(_Flaky(KeyError("gone"), "redo"), record=True) is True
    assert editor.history_manager.undo() is True

    assert editor.history_manager.redo() is False

    (entry,) = ledger.query().entries
    assert entry.operation == "Redo"


def test_an_undo_that_refuses_is_not_recorded(ledger, editor):
    assert editor._apply(_Flaky(Refusal("stale"), "undo"), record=True) is True

    assert editor.history_manager.undo() is False
    assert ledger.query().total == 0
