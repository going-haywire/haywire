"""Blocking tool routed through ctx.offload(): must not stall concurrent requests."""

import time

from haywire.core.farmhand import Farmhand, FarmhandContext, farmhand


@farmhand(
    label="Block",
    description="Sleep off-loop for `seconds`.",
    instructions="Sleep for `seconds` (default 1.0) off the event loop via ctx.offload(). "
    "Used to verify concurrent requests are not stalled by a blocking handler — not a real "
    "capability.",
    registry_id="block",
)
class BlockTool(Farmhand):
    async def run(self, ctx: FarmhandContext, seconds: float = 1.0) -> dict:
        start = time.monotonic()
        await ctx.offload(time.sleep, seconds)
        return {"slept": round(time.monotonic() - start, 3)}
