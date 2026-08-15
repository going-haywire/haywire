"""studio_get_errors / studio_dismiss_errors — query and triage the error ledger."""

from __future__ import annotations

from haywire.core.access import AccessTier
from haywire.core.errors.ledger import get_error_ledger
from haywire.core.farmhand import (
    Farmhand,
    FarmhandContext,
    FarmhandError,
    ToolAnnotations,
    farmhand,
    truncation_note,
)
from haywire.core.session.signals import ErrorLedgerChanged


@farmhand(
    label="Get errors",
    description="Query the studio's error ledger.",
    instructions="Query the studio's error ledger (since_seq/library/registry_key filters); "
    "results carry the current cursor for incremental polling and first_retained_seq "
    "so a client can detect when older history was evicted or deleted.",
    registry_id="get_errors",
    annotations=ToolAnnotations(read_only_hint=True),
    access=AccessTier.VIEW,
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
        note = truncation_note(len(result.entries), result.total, offset)
        return {
            "summary": f"{result.total} ledger entries match (cursor {result.cursor}).{note}",
            # The ledger holds live HaywireException objects; serialize each to a
            # JSON-friendly dict at this MCP boundary.
            "errors": [e.to_dict() for e in result.entries],
            "total": result.total,
            "cursor": result.cursor,
            # Smallest seq still retained; entries below it were evicted or
            # deleted. A client polling with since_seq below this has a gap.
            "first_retained_seq": result.first_retained_seq,
        }


@farmhand(
    label="Dismiss errors",
    description="Dismiss one or all ledger entries.",
    instructions="Dismiss ledger entries: pass seq=<n> to remove one, or all=true to clear every "
    "retained entry. Removal is permanent for that entry but leaves the monotonic cursor "
    "untouched, so incremental since_seq polling stays correct. Broadcasts so open studio "
    "Errors editors refresh. Dismissing an absent seq is a no-op (idempotent).",
    registry_id="dismiss_errors",
    annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=True),
    access=AccessTier.ADMIN,
)
class StudioDismissErrorsTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        seq: int | None = None,
        all: bool = False,
    ) -> dict:
        # Exactly one target: a single seq, or the whole retained window. Both
        # (or neither) is ambiguous — reject rather than guess.
        if all and seq is not None:
            raise FarmhandError(
                "invalid_args",
                "Pass either seq=<n> or all=true, not both.",
                {"seq": str(seq)},
                help=f"Retry with seq={seq} alone, or all=true alone.",
            )
        if not all and seq is None:
            raise FarmhandError(
                "invalid_args",
                "Pass seq=<n> to dismiss one entry, or all=true.",
                help="Run studio_get_errors to find the seq of the entry to dismiss.",
            )

        ledger = get_error_ledger()
        if all:
            before = ledger.query(limit=0).total
            ledger.clear()
            summary = f"Cleared {before} ledger entries."
        else:
            # delete() is a no-op if the seq is absent (already dismissed or
            # evicted) — mirror that in the summary rather than erroring.
            present = any(e.ledger_seq == seq for e in ledger.query(limit=ledger.current_seq).entries)
            ledger.delete(seq)  # type: ignore[arg-type]  # seq is not None on this branch
            summary = f"Dismissed entry {seq}." if present else f"No entry {seq} to dismiss."

        # Caller-owned cross-session refresh: ErrorLedgerChanged carries no
        # payload — every session's Errors editor re-reads the ledger. Matches
        # the editor's own mutate-then-broadcast triage contract.
        ctx.broadcast(ErrorLedgerChanged())
        return {"summary": summary, "cursor": ledger.current_seq}
