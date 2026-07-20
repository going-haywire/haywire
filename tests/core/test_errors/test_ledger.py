"""Unit tests for the bounded, sequence-numbered error ledger."""

import pytest

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.errors.ledger import ErrorLedger, set_error_ledger
from haywire.core.library.identity import LibraryIdentity

pytestmark = pytest.mark.unit


def _identity(lib_id: str = "testing") -> LibraryIdentity:
    return LibraryIdentity(
        label=lib_id,
        version="0.1",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        folder_path="/tmp/fake",
        module_name=lib_id,
        id=lib_id,
    )


@pytest.fixture()
def ledger():
    fresh = ErrorLedger(max_entries=5)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(None)


def _exc(msg: str, **kwargs) -> HaywireException:
    return HaywireException.create(msg, **kwargs)


def test_record_assigns_monotonic_sequence(ledger):
    first = ledger.record(_exc("one"))
    second = ledger.record(_exc("two"))
    assert second == first + 1
    assert ledger.current_seq == second


def test_query_returns_entries_with_cursor(ledger):
    ledger.record(_exc("boom", registry_key="testing:node:foo"))
    page = ledger.query()
    assert page.total == 1
    assert page.cursor == ledger.current_seq
    entry = page.entries[0]
    assert entry["message"] == "boom"
    assert entry["registry_key"] == "testing:node:foo"
    assert entry["seq"] == ledger.current_seq


def test_query_since_seq_excludes_older(ledger):
    ledger.record(_exc("old"))
    marker = ledger.current_seq
    ledger.record(_exc("new"))
    page = ledger.query(since_seq=marker)
    assert page.total == 1
    assert page.entries[0]["message"] == "new"


def test_query_filters_by_library_and_registry_key(ledger):
    ledger.record(_exc("a", library_identity=_identity("testing")))
    ledger.record(_exc("b", registry_key="other:node:bar"))
    assert ledger.query(library="testing").total == 1
    assert ledger.query(registry_key="other:node:bar").total == 1
    assert ledger.query(library="nope").total == 0


def test_bounded_drops_oldest(ledger):
    for i in range(8):  # max_entries=5
        ledger.record(_exc(f"e{i}"))
    page = ledger.query(limit=100)
    assert page.total == 5
    assert page.entries[0]["message"] == "e3"  # oldest surviving
    # Sequence numbers keep climbing even though entries drop.
    assert ledger.current_seq == 8


def test_query_pagination(ledger):
    for i in range(5):
        ledger.record(_exc(f"e{i}"))
    page = ledger.query(limit=2, offset=2)
    assert page.total == 5
    assert [e["message"] for e in page.entries] == ["e2", "e3"]


def test_log_registers_in_ambient_ledger(ledger):
    exc = _exc("logged error")
    exc.log()
    assert ledger.query().total == 1
    assert ledger.query().entries[0]["message"] == "logged error"


def test_log_without_ledger_does_not_crash():
    set_error_ledger(None)
    _exc("no ledger").log()  # must not raise
