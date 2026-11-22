"""Canned failing tool: exercises the structured error contract."""

from __future__ import annotations

from haywire.api.workbench import AccessTier, Farmhand, FarmhandContext, FarmhandError, farmhand


@farmhand(
    label="Fail",
    description="Always fails with a stable code.",
    instructions="Always raises a FarmhandError with code 'testing_failure'. Used to exercise "
    "the structured error contract in tests — not a real capability. Never call this "
    "expecting a result.",
    registry_id="fail",
    requires=AccessTier.VIEW,
)
class FailTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        raise FarmhandError("testing_failure", "This tool always fails.", ids={"tool": "fail"})
