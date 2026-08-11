"""Canned failing tool: exercises the structured error contract."""

from haywire.core.farmhand import Farmhand, FarmhandContext, FarmhandError, farmhand


# --8<-- [start:fail_tool]
@farmhand(
    label="Fail",
    description="Always fails with a stable code.",
    instructions="Always raises a FarmhandError with code 'testing_failure'. Used to exercise "
    "the structured error contract in tests — not a real capability. Never call this "
    "expecting a result.",
    registry_id="fail",
)
class FailTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        raise FarmhandError("testing_failure", "This tool always fails.", ids={"tool": "fail"})


# --8<-- [end:fail_tool]
