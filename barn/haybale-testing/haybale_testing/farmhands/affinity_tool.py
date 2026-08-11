"""Instrumented tool: reports which thread/loop the handler ran on (ticket 06 evidence)."""

import asyncio
import threading

from haywire.core.farmhand import Farmhand, FarmhandContext, ToolAnnotations, farmhand


@farmhand(
    label="Affinity",
    description="Report handler thread and loop.",
    instructions="Report which thread and asyncio loop the handler ran on. Read-only, no "
    "side effects — used to verify Farmhand call-path threading behavior in tests, not a "
    "real capability.",
    registry_id="affinity",
    annotations=ToolAnnotations(read_only_hint=True),
)
class AffinityTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        try:
            on_loop = asyncio.get_running_loop() is not None
        except RuntimeError:
            on_loop = False
        return {"thread": threading.current_thread().name, "on_event_loop": on_loop}
