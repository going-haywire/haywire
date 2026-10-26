"""Unit tests for ``Refusal`` and the error-boundary helpers."""

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
    assert logged.error_context["action"] == "Move"
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
    assert loss.severity is ErrorSeverity.WARNING
    assert ledger.query().total == 1
    assert loss.graph_id == "g1"
