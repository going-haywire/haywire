"""haystack_* MCP tools: graph lifecycle + execution control (spec §5)."""

from __future__ import annotations

from haywire.core.farmhand import (
    Farmhand,
    FarmhandContext,
    FarmhandError,
    ToolAnnotations,
    farmhand,
    truncation_note,
)
from haywire.core.session.signals import GraphDataMutated

_READ_ONLY = ToolAnnotations(read_only_hint=True)
_MUTATING = ToolAnnotations()


def _state(ctx: FarmhandContext):
    from haybale_haystack.state.haystack_state import HaystackState

    return ctx.state(HaystackState)


def _entry(ctx: FarmhandContext, binding_id: str):
    entry = _state(ctx).get_by_id(binding_id)
    if entry is None:
        raise FarmhandError(
            "graph_not_found", f"No open graph '{binding_id}'.", ids={"binding_id": binding_id}
        )
    return entry


def _entry_row(entry) -> dict:
    return {
        "binding_id": entry.binding_id,
        "display_name": entry.display_name,
        "path": str(entry.path) if entry.path else None,
        "unsaved": entry.unsaved,
        "is_executing": entry.is_executing,
    }


def _compile_row(result) -> dict:
    # CompileResult carries ok: bool and error: str | None (execution/compile_result.py).
    return {"ok": result.ok, "error": result.error}


@farmhand(
    label="List graphs",
    description="Open haystack entries plus .haywire files on disk in the workspace.",
    registry_id="list_graphs",
    annotations=_READ_ONLY,
)
class HaystackListGraphsTool(Farmhand):
    async def run(self, ctx: FarmhandContext, limit: int = 100, offset: int = 0) -> dict:
        open_rows = [_entry_row(e) for e in _state(ctx).all_entries()]
        root = ctx.workspace_root()
        on_disk = sorted(
            str(p.relative_to(root))
            for p in root.rglob("*.haywire")
            if not any(part.startswith(".") for part in p.relative_to(root).parts)
        )
        total = len(on_disk)
        files = on_disk[offset : offset + limit]
        return {
            "summary": (
                f"{len(open_rows)} graphs open, {total} .haywire files on disk."
                f"{truncation_note(len(files), total, offset)}"
            ),
            "open": open_rows,
            "files": files,
            "total": total,
        }


@farmhand(
    label="Create graph",
    description="Create a new untitled graph (appears in open browser sessions).",
    registry_id="create_graph",
    annotations=_MUTATING,
)
class HaystackCreateGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        entry = _state(ctx).create_new()  # broadcasts GraphDataMutated itself
        return {"summary": f"Created {entry.binding_id}.", **_entry_row(entry)}


@farmhand(
    label="Open graph",
    description="Open a .haywire file (idempotent per path).",
    registry_id="open_graph",
    annotations=_MUTATING,
)
class HaystackOpenGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, path: str) -> dict:
        target = (ctx.workspace_root() / path).resolve()
        if not target.exists():
            raise FarmhandError("file_not_found", f"No file at {target}.", ids={"path": path})
        entry = _state(ctx).open_graph(target)
        return {"summary": f"Opened {entry.binding_id}.", **_entry_row(entry)}


@farmhand(
    label="Save graph",
    description="Save an open graph; save_as writes to a new path.",
    registry_id="save_graph",
    annotations=_MUTATING,
)
class HaystackSaveGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str, save_as: str | None = None) -> dict:
        entry = _entry(ctx, binding_id)
        target = (ctx.workspace_root() / save_as).resolve() if save_as else None
        if target is not None:
            target.parent.mkdir(parents=True, exist_ok=True)
        ok = _state(ctx).save_graph(entry, target)
        if not ok:
            raise FarmhandError(
                "save_failed", f"Saving '{binding_id}' failed.", ids={"binding_id": binding_id}
            )
        return {"summary": f"Saved {entry.binding_id}.", **_entry_row(entry)}


@farmhand(
    label="Rename graph",
    description="Rename an open graph's file on disk and rekey it.",
    registry_id="rename_graph",
    annotations=_MUTATING,
)
class HaystackRenameGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str, new_name: str) -> dict:
        entry = _entry(ctx, binding_id)
        ok = _state(ctx).rename_graph(entry, new_name)
        if not ok:
            raise FarmhandError(
                "rename_failed", f"Renaming '{binding_id}' failed.", ids={"binding_id": binding_id}
            )
        return {"summary": f"Renamed to {entry.display_name}.", **_entry_row(entry)}


@farmhand(
    label="Close graph",
    description="Close an open graph entry. NEVER deletes the file on disk.",
    registry_id="close_graph",
    annotations=_MUTATING,
)
class HaystackCloseGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        entry = _entry(ctx, binding_id)
        _state(ctx).remove_entry(entry)
        return {"summary": f"Closed {binding_id} (file kept).", "binding_id": binding_id}


@farmhand(
    label="Compile graph",
    description="Compile without starting; returns compile diagnostics.",
    registry_id="compile_graph",
    annotations=_READ_ONLY,
)
class HaystackCompileGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        result = _entry(ctx, binding_id).compile()
        return {"summary": f"Compiled {binding_id}.", "compile": _compile_row(result)}


@farmhand(
    label="Start graph",
    description="Compile and start execution. Destructive: nodes perform real I/O.",
    registry_id="start_graph",
    annotations=ToolAnnotations(destructive_hint=True),
)
class HaystackStartGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        entry = _entry(ctx, binding_id)
        result = _state(ctx).start_execution(entry)
        ctx.broadcast(GraphDataMutated())  # start/stop don't broadcast themselves
        return {
            "summary": f"Started {binding_id}.",
            "compile": _compile_row(result),
            **_entry_row(entry),
        }


@farmhand(
    label="Stop graph",
    description="Stop a running graph (bounded grace, then teardown).",
    registry_id="stop_graph",
    annotations=_MUTATING,
)
class HaystackStopGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        entry = _entry(ctx, binding_id)
        _state(ctx).stop_execution(entry)
        ctx.broadcast(GraphDataMutated())
        return {"summary": f"Stopped {binding_id}.", **_entry_row(entry)}
