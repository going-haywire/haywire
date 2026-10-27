"""Unit tests for ``Refusal`` and the error-boundary helpers."""

import logging

import pytest

from haywire.core.errors import ErrorSeverity, HaywireException, Refusal, report_failure, report_loss
from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire.core.farmhand.errors import FarmhandError

pytestmark = pytest.mark.unit


@pytest.fixture
def ledger():
    previous = get_error_ledger()
    fresh = ErrorLedger(max_entries=5)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(previous)


def test_a_refusal_is_not_recorded(ledger):
    assert report_failure(Refusal("stale"), operation="Apply edit") is None
    assert ledger.query().total == 0


def test_a_refusal_is_recorded_when_refusals_fail(ledger):
    logged = report_failure(Refusal("x"), operation="Signal handler", refusals_fail=True)
    assert logged is not None
    assert logged.ledger_seq > 0
    assert ledger.query().total == 1


def test_a_plain_exception_is_wrapped_enriched_and_recorded(ledger):
    logged = report_failure(
        KeyError("x"), operation="Apply edit", graph_id="g1", node_id="n1", action="Move"
    )
    assert logged is not None
    assert logged.ledger_seq > 0
    assert (logged.operation, logged.graph_id, logged.node_id) == ("Apply edit", "g1", "n1")
    assert logged.details["action"] == "Move"
    assert logged.message == "Apply edit failed"


def test_an_existing_haywire_exception_is_reused_not_wrapped(ledger):
    inner = HaywireException.create("build failed", node_id="n1", operation="build")
    assert report_failure(inner, operation="Apply edit", node_id="n2", graph_id="g1") is inner
    assert (inner.node_id, inner.operation, inner.graph_id) == ("n1", "build", "g1")


def test_an_already_logged_exception_adds_no_entry(ledger):
    inner = HaywireException.create("build failed").log()
    report_failure(inner, operation="Apply edit")
    assert ledger.query().total == 1


def test_report_failure_never_raises(ledger, monkeypatch):
    monkeypatch.setattr(HaywireException, "log", lambda self, logger=None: 1 / 0)
    assert report_failure(RuntimeError("x"), operation="Apply edit") is None


def test_a_farmhand_error_is_a_refusal():
    err = FarmhandError("code", "msg")
    assert isinstance(err, Refusal)
    assert str(err) == "msg"
    assert err.message == "msg"


def test_report_loss_records_a_warning(ledger):
    loss = report_loss("setup lost", operation="Hot reload", graph_id="g1")
    assert loss is not None
    assert loss.severity is ErrorSeverity.WARNING
    assert ledger.query().total == 1
    assert loss.graph_id == "g1"


def test_report_loss_never_raises(ledger, monkeypatch):
    monkeypatch.setattr(HaywireException, "log", lambda self, logger=None: 1 / 0)
    assert report_loss("setup lost", operation="Hot reload") is None


def test_a_refusal_let_through_is_logged_at_info(ledger, caplog):
    with caplog.at_level(logging.INFO, logger="haywire.core.errors.boundary"):
        assert report_failure(Refusal("Node is gone"), operation="Apply edit") is None
    assert any(
        r.levelno == logging.INFO and r.getMessage() == "Apply edit refused: Node is gone"
        for r in caplog.records
    )


def _raise_here() -> None:
    raise KeyError("a")


def _raise_there() -> None:
    raise KeyError("a")


def _report(raiser) -> None:
    try:
        raiser()
    except KeyError as e:
        report_failure(e, operation="Apply edit")


def test_the_same_failure_from_two_lines_makes_two_entries(ledger):
    _report(_raise_here)
    _report(_raise_there)
    assert ledger.query().total == 2


def test_the_same_raise_twice_makes_one_entry_counted_twice(ledger):
    _report(_raise_here)
    _report(_raise_here)
    (entry,) = ledger.query().entries
    assert entry.count == 2


def test_the_detailed_report_shows_the_boundary_context(ledger):
    logged = report_failure(
        KeyError("x"), operation="Apply edit", graph_id="g1", node_id="n1", edge_id="e1", file_path="/a/b"
    )
    assert logged is not None
    report = logged.format_detailed()
    for line in ("Graph     : g1", "Node      : n1", "Edge      : e1", "File path : /a/b"):
        assert line in report
    assert logged.to_dict()["details"] == {"file_path": "/a/b"}


def test_module_name_sets_the_field_not_the_details(ledger):
    logged = report_failure(KeyError("x"), operation="Hot reload", module_name="pkg.mod")
    assert logged is not None
    assert logged.module_name == "pkg.mod"
    assert "module_name" not in logged.details
