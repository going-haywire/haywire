"""studio_status — orientation floor for a connecting agent."""

from __future__ import annotations

from importlib.metadata import version as pkg_version

from haywire.core.farmhand import Farmhand, FarmhandContext, ToolAnnotations, farmhand
from haywire.core.library.registry import LibraryRegistry


def _version(dist: str) -> str:
    try:
        return pkg_version(dist)
    except Exception:
        return "unknown"


@farmhand(
    label="Studio status",
    description="Versions, workspace root, enabled-library and open-graph counts, docs URL.",
    registry_id="status",
    annotations=ToolAnnotations(read_only_hint=True),
)
class StudioStatusTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        registry = ctx.registry(LibraryRegistry)
        enabled = [lib for lib in registry.list_names() if registry.is_library_enabled(lib)]
        open_graphs = 0
        try:  # haystack is a library, absent on a bare studio
            from haybale_haystack.state.haystack_state import HaystackState

            open_graphs = len(ctx.state(HaystackState).all_entries())
        except Exception:
            pass
        return {
            "summary": f"Haywire studio at {ctx.workspace_root()}: "
            f"{len(enabled)} libraries enabled, {open_graphs} graphs open.",
            "haywire_core_version": _version("haywire-core"),
            "haywire_studio_version": _version("haywire-studio"),
            "protocol_version": "2025-11-25",
            "workspace_root": str(ctx.workspace_root()),
            "enabled_libraries": len(enabled),
            "open_graphs": open_graphs,
            "docs_url": "https://github.com/going-haywire/haywire",
        }
