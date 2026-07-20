"""Blocking tool routed through ctx.offload(): must not stall concurrent requests."""

import time

from haywire.core.farmhand import Farmhand, FarmhandContext, farmhand


@farmhand(label="Block", description="Sleep off-loop for `seconds`.", registry_id="block")
class BlockTool(Farmhand):
    async def run(self, ctx: FarmhandContext, seconds: float = 1.0) -> dict:
        start = time.monotonic()
        await ctx.offload(time.sleep, seconds)
        return {"slept": round(time.monotonic() - start, 3)}
