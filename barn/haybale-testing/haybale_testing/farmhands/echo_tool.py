"""Canned read tool for Farmhand integration tests."""

from haywire.core.farmhand import Farmhand, FarmhandContext, ToolAnnotations, farmhand


@farmhand(
    label="Echo",
    description="Echo text back (canned read tool).",
    registry_id="echo",
    annotations=ToolAnnotations(read_only_hint=True),
)
class EchoTool(Farmhand):
    async def run(self, ctx: FarmhandContext, text: str) -> dict:
        return {"echo": text}
