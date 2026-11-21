"""Blocking tool routed through ctx.offload(): must not stall concurrent requests."""

import threading
import time

from haywire.api.workbench import AccessTier, Farmhand, FarmhandContext, farmhand

_gates: dict[str, threading.Event] = {}
_gates_lock = threading.Lock()


def _gate(name: str) -> threading.Event:
    with _gates_lock:
        return _gates.setdefault(name, threading.Event())


@farmhand(
    label="Block",
    description="Sleep off-loop for `seconds`, or until `gate` is released.",
    instructions="Sleep for `seconds` (default 1.0) off the event loop via ctx.offload(). With "
    "`gate`, wait off-loop until the Release tool opens that gate, giving up after `seconds`. "
    "Used to verify concurrent requests are not stalled by a blocking handler — not a real "
    "capability.",
    registry_id="block",
    requires=AccessTier.VIEW,
)
class BlockTool(Farmhand):
    async def run(self, ctx: FarmhandContext, seconds: float = 1.0, gate: str | None = None) -> dict:
        start = time.monotonic()
        if gate is None:
            await ctx.offload(time.sleep, seconds)
            return {"slept": round(time.monotonic() - start, 3)}
        event = _gate(gate)
        released = await ctx.offload(event.wait, seconds)
        with _gates_lock:
            _gates.pop(gate, None)
        return {"released": released, "slept": round(time.monotonic() - start, 3)}


@farmhand(
    label="Release",
    description="Open a gate a Block call waits on.",
    instructions="Open the gate named `gate` if a Block call is waiting on it. Returns "
    "`released: false` when no Block call waits on that gate yet. Used with Block to verify "
    "concurrent requests are not stalled — not a real capability.",
    registry_id="release",
    requires=AccessTier.VIEW,
)
class ReleaseTool(Farmhand):
    async def run(self, ctx: FarmhandContext, gate: str) -> dict:
        with _gates_lock:
            event = _gates.get(gate)
        if event is None:
            return {"released": False}
        event.set()
        return {"released": True}
