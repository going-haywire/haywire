"""Instrumented tool: reports which thread/loop the handler ran on (ticket 06 evidence)."""

import asyncio
import threading

from haywire.core.farmhand import Farmhand, FarmhandContext, ToolAnnotations, farmhand


@farmhand(
    label="Affinity",
    description="Report handler thread and loop.",
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
