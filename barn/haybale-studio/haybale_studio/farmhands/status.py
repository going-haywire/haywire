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
    description="Versions, workspace root, enabled-library counts, docs manifest "
    "URI. Call this first when connecting — the summary points at how to find documentation.",
    registry_id="status",
    annotations=ToolAnnotations(read_only_hint=True),
)
class StudioStatusTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        registry = ctx.registry(LibraryRegistry)
        enabled = [lib for lib in registry.list_names() if registry.is_library_enabled(lib)]
        return {
            "summary": f"Haywire studio at {ctx.workspace_root()}: "
            f"{len(enabled)} libraries enabled. Docs are served as "
            "MCP resources — read farmhand://docs/_manifest for the full index (path + title "
            "per doc) before guessing a doc path.",
            "haywire_core_version": _version("haywire-core"),
            "haywire_studio_version": _version("haywire-studio"),
            "protocol_version": "2025-11-25",
            "workspace_root": str(ctx.workspace_root()),
            "enabled_libraries": len(enabled),
            "docs_manifest_uri": "farmhand://docs/_manifest",
            "docs_url": "https://github.com/going-haywire/haywire",
        }
