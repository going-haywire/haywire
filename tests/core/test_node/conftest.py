"""Fixtures shared by the node tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def construction_fails(monkeypatch):
    """Make ``TestPrintNode`` construction raise for the next ``n`` calls (``arm(n)``)."""
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    original = TestPrintNode.__init__
    state = {"left": 0}

    def flaky(self, *args, **kwargs):
        if state["left"] > 0:
            state["left"] -= 1
            raise RuntimeError("construction failed")
        original(self, *args, **kwargs)

    monkeypatch.setattr(TestPrintNode, "__init__", flaky)

    def arm(n: int = 1) -> None:
        state["left"] = n

    return arm
