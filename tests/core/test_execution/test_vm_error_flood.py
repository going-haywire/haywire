"""A node failing on every frame leaves one ledger entry, not one per frame."""

from unittest.mock import MagicMock

import pytest

from haywire.core.errors.ledger import ErrorLedger, set_error_ledger
from haywire.core.execution.vm import HaywireVM

pytestmark = pytest.mark.unit


@pytest.fixture
def ledger():
    fresh = ErrorLedger(max_entries=500)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(None)


def test_a_node_failing_every_run_leaves_one_entry(ledger):
    node = MagicMock()
    node.node_id = "n1"
    node.identity.label = "Boom"
    node.identity.registry_key = "lib:node:boom"
    vm = HaywireVM.__new__(HaywireVM)
    for _ in range(1000):
        try:
            raise RuntimeError("frame 42 broke")
        except RuntimeError as exc:
            vm.catch_exception(exc, node, "Node Execution")
    page = ledger.query()
    assert page.total == 1
    assert page.entries[0].count == 1000
