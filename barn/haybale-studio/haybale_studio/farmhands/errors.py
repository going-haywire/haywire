"""studio_get_errors — query the error ledger."""

from __future__ import annotations

from haywire.core.errors.ledger import get_error_ledger
from haywire.core.farmhand import Farmhand, FarmhandContext, ToolAnnotations, farmhand


@farmhand(
    label="Get errors",
    description="Query the studio's error ledger (since_seq/library/registry_key filters); "
    "results carry the current cursor for incremental polling and first_retained_seq "
    "so a client can detect when older history was evicted or deleted.",
    registry_id="get_errors",
    annotations=ToolAnnotations(read_only_hint=True),
)
class StudioGetErrorsTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        since_seq: int | None = None,
        library: str | None = None,
        registry_key: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        result = get_error_ledger().query(
            since_seq=since_seq,
            library=library,
            registry_key=registry_key,
            limit=limit,
            offset=offset,
        )
        return {
            "summary": f"{result.total} ledger entries match (cursor {result.cursor}).",
            # The ledger holds live HaywireException objects; serialize each to a
            # JSON-friendly dict at this MCP boundary.
            "errors": [e.to_dict() for e in result.entries],
            "total": result.total,
            "cursor": result.cursor,
            # Smallest seq still retained; entries below it were evicted or
            # deleted. A client polling with since_seq below this has a gap.
            "first_retained_seq": result.first_retained_seq,
        }
