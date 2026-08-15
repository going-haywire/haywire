"""haystack_* MCP tools: graph lifecycle + execution control (spec §5)."""

from __future__ import annotations

from haywire.core.access import AccessTier
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
            "graph_not_found",
            f"No open graph '{binding_id}'.",
            ids={"binding_id": binding_id},
            help="Run haystack_list_graphs to see open graphs, or haystack_open_graph to open one.",
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
    instructions="List open graph sessions (with their binding_id, needed by every other "
    "haystack_*/graph_editor_* tool) plus every .haywire file found on disk under the workspace "
    "root, whether open or not. Use this first to discover a binding_id, or to find a file path "
    "to pass to haystack_open_graph.",
    registry_id="list_graphs",
    annotations=_READ_ONLY,
    access=AccessTier.VIEW,
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
        result = {
            "summary": (
                f"{len(open_rows)} graphs open, {total} .haywire files on disk."
                f"{truncation_note(len(files), total, offset)}"
            ),
            "open": open_rows,
            "files": files,
            "total": total,
        }
        if open_rows:
            result["help"] = (
                "Run graph_editor_query_graph binding_id=<id> to inspect an open graph, or "
                "haystack_open_graph path=<path> to open one of the files on disk."
            )
        elif files:
            result["help"] = "Run haystack_open_graph path=<path> to open one, or haystack_create_graph."
        else:
            result["help"] = "Run haystack_create_graph to start a new graph."
        return result


@farmhand(
    label="Create graph",
    description="Create a new untitled graph (appears in open browser sessions).",
    instructions="Create a new untitled, unsaved graph and return its binding_id. The graph "
    "appears in any open studio browser session immediately. It has no nodes yet — follow with "
    "graph_editor_add_node, then haystack_save_graph (it stays unsaved until you do).",
    registry_id="create_graph",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
)
class HaystackCreateGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        entry = _state(ctx).create_new()  # broadcasts GraphDataMutated itself
        return {
            "summary": f"Created {entry.binding_id}.",
            **_entry_row(entry),
            "help": (
                f"Run graph_editor_add_node binding_id={entry.binding_id!r} registry_key=<key> to "
                f"populate it, then haystack_save_graph binding_id={entry.binding_id!r} path=<path> "
                f"(it is unsaved until you do)."
            ),
        }


@farmhand(
    label="Open graph",
    description="Open a .haywire file (idempotent per path).",
    instructions="Open a .haywire file by path, relative to the workspace root, and return its "
    "binding_id. Idempotent: opening an already-open path returns the same session rather than "
    "duplicating it. Raises file_not_found if the path doesn't exist — run haystack_list_graphs "
    "to see valid paths.",
    registry_id="open_graph",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
)
class HaystackOpenGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, path: str) -> dict:
        target = (ctx.workspace_root() / path).resolve()
        if not target.exists():
            raise FarmhandError(
                "file_not_found",
                f"No file at {target}.",
                ids={"path": path},
                help="Run haystack_list_graphs to see graph files in the haystack.",
            )
        entry = _state(ctx).open_graph(target)
        return {"summary": f"Opened {entry.binding_id}.", **_entry_row(entry)}


@farmhand(
    label="Save graph",
    description="Save an open graph; save_as writes to a new path.",
    instructions="Save an open graph (by binding_id) to its current path. Pass save_as=<path> "
    "(relative to the workspace root) to write to a new path instead — e.g. to save an untitled "
    "graph from haystack_create_graph for the first time. Raises graph_not_found for an unknown "
    "binding_id, save_failed if the write itself fails.",
    registry_id="save_graph",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
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
    instructions="Rename an open graph: renames its file on disk to new_name and updates its "
    "display_name. The binding_id itself does not change. Raises graph_not_found for an unknown "
    "binding_id, rename_failed if the rename itself fails (e.g. name collision).",
    registry_id="rename_graph",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
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
    instructions="Close an open graph session by binding_id, removing it from the open-entries "
    "list. NEVER deletes the file on disk — the graph can be reopened later with "
    "haystack_open_graph. Raises graph_not_found for an unknown binding_id.",
    registry_id="close_graph",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
)
class HaystackCloseGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        entry = _entry(ctx, binding_id)
        _state(ctx).remove_entry(entry)
        return {"summary": f"Closed {binding_id} (file kept).", "binding_id": binding_id}


@farmhand(
    label="Compile graph",
    description="Compile without starting; returns compile diagnostics.",
    instructions="Compile an open graph WITHOUT starting execution — use this to check for "
    "compile errors before haystack_start_graph, since starting a broken graph wastes the "
    "destructive-side-effects warning for nothing. Returns compile.ok and compile.error (null "
    "when ok).",
    registry_id="compile_graph",
    annotations=_READ_ONLY,
    access=AccessTier.VIEW,
)
class HaystackCompileGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        result = _entry(ctx, binding_id).compile()
        return {"summary": f"Compiled {binding_id}.", "compile": _compile_row(result)}


@farmhand(
    label="Start graph",
    description="Compile and start execution. Destructive: nodes perform real I/O.",
    instructions="Compile and start executing an open graph. DESTRUCTIVE — nodes perform real "
    "I/O once running (hardware, network, file writes), not a dry run. Consider "
    "haystack_compile_graph first to catch compile errors without side effects. Follow with "
    "haystack_stop_graph when done.",
    registry_id="start_graph",
    annotations=ToolAnnotations(destructive_hint=True),
    access=AccessTier.EDIT,
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
    instructions="Stop a running graph by binding_id: gives nodes a bounded grace period to "
    "shut down cleanly, then tears down execution. Safe to call on a graph that is not "
    "currently running.",
    registry_id="stop_graph",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
)
class HaystackStopGraphTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        entry = _entry(ctx, binding_id)
        _state(ctx).stop_execution(entry)
        ctx.broadcast(GraphDataMutated())
        return {"summary": f"Stopped {binding_id}.", **_entry_row(entry)}
