"""Farmhand's tool runner is an error boundary: failures reach the ledger, refusals do not."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from haywire.core.di.context import set_error_ledger
from haywire.core.errors import Refusal
from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.errors.ledger import ErrorLedger
from haywire.core.farmhand import Farmhand, FarmhandError


@pytest.fixture
def ledger():
    fresh = ErrorLedger()
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(None)


@pytest.fixture
def raising_tool(farmhand_server):
    """Register a tool that raises whatever the test sets, and remove it afterwards."""
    box: dict[str, Exception] = {}

    class RaisingTool(Farmhand):
        # A hand-built double: the SDK's cached tool listing reads these two.
        class_identity = SimpleNamespace(  # type: ignore[assignment]
            instructions="raises on demand", annotations=SimpleNamespace(to_dict=dict)
        )

        async def run(self, ctx, **kwargs):
            raise box["exc"]

        @classmethod
        def input_schema(cls):
            return {"type": "object"}

    farmhand_server.host._tools["raising"] = RaisingTool
    yield box
    farmhand_server.host._tools.pop("raising", None)


def _call(farmhand_call) -> str:
    async def scenario(session, init):
        return await session.call_tool("raising", {"secret": "value"})

    result = farmhand_call(scenario)
    assert result.isError is True
    return result.content[0].text


def test_a_failing_tool_is_recorded_and_the_agent_sees_its_seq(farmhand_call, raising_tool, ledger):
    raising_tool["exc"] = KeyError("boom")
    text = _call(farmhand_call)
    entries = ledger.query().entries
    assert len(entries) == 1
    assert text.startswith("[internal]")
    assert text.endswith(f" (ledger_seq={entries[0].ledger_seq})")
    assert entries[0].details["tool"] == "raising"
    assert entries[0].details["arguments"] == ["secret"]
    assert "value" not in str(entries[0].details)


def test_a_farmhand_error_is_not_recorded(farmhand_call, raising_tool, ledger):
    raising_tool["exc"] = FarmhandError("some_code", "Nope.", ids={"tool": "raising"})
    assert _call(farmhand_call) == "[some_code] Nope. (tool=raising)"
    assert ledger.query().entries == []


def test_a_plain_refusal_renders_as_refused(farmhand_call, raising_tool, ledger):
    raising_tool["exc"] = Refusal("stale id")
    assert _call(farmhand_call) == "[refused] stale id"
    assert ledger.query().entries == []


def test_a_haywire_exception_from_a_tool_keeps_its_category_and_gains_the_seq(
    farmhand_call, raising_tool, ledger
):
    raising_tool["exc"] = HaywireException(message="bad node", category="Node Load Error")
    text = _call(farmhand_call)
    entries = ledger.query().entries
    assert len(entries) == 1
    assert text == f"[haywire:Node Load Error] bad node (ledger_seq={entries[0].ledger_seq})"
