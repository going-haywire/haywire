"""`StepFlow.advance()` — dispatch by current step name.

Exists so `show_step_flow(auto_start=True)` can drive a flow without knowing
which step is current. Panels keep calling their own `advance_from_*`
directly; most take arguments, which this dispatch cannot supply.
"""

from __future__ import annotations

import pytest

from haywire.ui.components.stepper import StepFlow

pytestmark = [pytest.mark.unit, pytest.mark.anyio]


@pytest.fixture
def anyio_backend() -> str:
    """anyio's backend parametrization. The repo runs asyncio only."""
    return "asyncio"


class _Flow(StepFlow):
    STEPS = ("first", "second", "done")
    STEP_TITLES = {"first": "First", "second": "Second", "done": "Done"}

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    async def advance_from_first(self) -> None:
        self.calls.append("first")
        self.step = "second"

    async def advance_from_second(self) -> None:
        self.calls.append("second")
        self.step = "done"


async def test_advance_runs_the_current_steps_method() -> None:
    flow = _Flow()

    await flow.advance()

    assert flow.calls == ["first"]
    assert flow.step == "second"


async def test_advance_follows_the_step_it_lands_on() -> None:
    """Dispatch is re-read each call, not bound once — otherwise auto_start
    would re-run the first step forever."""
    flow = _Flow()

    await flow.advance()
    await flow.advance()

    assert flow.calls == ["first", "second"]
    assert flow.step == "done"


async def test_advance_raises_for_a_step_with_no_method() -> None:
    """The terminal step has no advance_from_*; naming it is better than a
    silent no-op, which would look like a flow that hung."""
    flow = _Flow()
    flow.step = "done"

    with pytest.raises(AttributeError, match="advance_from_done"):
        await flow.advance()
