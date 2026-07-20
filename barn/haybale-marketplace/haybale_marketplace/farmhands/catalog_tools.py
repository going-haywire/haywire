"""marketplace_list_available / marketplace_refresh / marketplace_get_library_docs."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path

from haywire.core.farmhand import (
    Farmhand,
    FarmhandContext,
    FarmhandError,
    ToolAnnotations,
    farmhand,
)
from haywire.core.library.registry import LibraryRegistry

_DOC_FILES = ("OVERVIEW.md", "QUICKREF.md", "README.md")


def _marketplace_state(ctx: FarmhandContext):
    from haybale_marketplace.state.marketplace_state import MarketplaceState

    return ctx.state(MarketplaceState)


def _library_manager(ctx: FarmhandContext):
    from haybale_marketplace.state.library_manager_state import LibraryManagerState

    state = ctx.state(LibraryManagerState)
    manager = state.manager
    if manager is None:
        raise FarmhandError("marketplace_unavailable", "LibraryManager is not initialized on this studio.")
    return manager


def _progress_cb(ctx: FarmhandContext):
    """Bridge LibraryManager's sync on_output callback to async ctx.progress."""
    loop = asyncio.get_running_loop()

    def on_output(line: str) -> None:
        loop.create_task(ctx.progress(line))

    return on_output


@farmhand(
    label="List available",
    description="Merged AVAILABLE catalog (not-installed libraries) from the marketplace cache.",
    registry_id="list_available",
    annotations=ToolAnnotations(read_only_hint=True),
)
class MarketplaceListAvailableTool(Farmhand):
    async def run(self, ctx: FarmhandContext, limit: int = 50, offset: int = 0) -> dict:
        haybales = [asdict(h) for h in _marketplace_state(ctx).get_project_haybales()]
        total = len(haybales)
        return {
            "summary": f"{total} haybales available.",
            "haybales": haybales[offset : offset + limit],
            "total": total,
        }


@farmhand(
    label="Refresh catalog",
    description="Re-fetch all subscribed markets/stalls (network; rewrites the project cache).",
    registry_id="refresh",
    annotations=ToolAnnotations(open_world_hint=True),
)
class MarketplaceRefreshTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        state = _marketplace_state(ctx)
        report = await ctx.offload(state.refresh)  # blocking urllib — never on the loop
        return {
            "summary": f"Refreshed: {report.haybales_resolved} haybales resolved.",
            "report": {k: v for k, v in vars(report).items() if not k.startswith("_")},
        }


@farmhand(
    label="Get library docs",
    description="Docs for an installed library (OVERVIEW/QUICKREF/README from its folder) or an "
    "available one (network fetch of its docs_url).",
    registry_id="get_library_docs",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True),
)
class MarketplaceGetLibraryDocsTool(Farmhand):
    async def run(self, ctx: FarmhandContext, library: str) -> dict:
        registry = ctx.registry(LibraryRegistry)
        if library in registry.list_names():
            folder = Path(registry.get_library_identity(library).folder_path)
            for name in _DOC_FILES:
                path = folder / name
                if path.exists():
                    return {
                        "summary": f"{library}: {name} ({path.stat().st_size} bytes).",
                        "source": "installed",
                        "file": name,
                        "text": path.read_text(encoding="utf-8"),
                    }
            raise FarmhandError(
                "docs_not_found",
                f"'{library}' ships no OVERVIEW/QUICKREF/README.",
                ids={"library": library},
            )
        for pkg in _marketplace_state(ctx).get_project_haybales():
            if pkg.name == library:
                text = await _marketplace_state(ctx).fetch_overview(pkg)
                if not text:
                    raise FarmhandError(
                        "docs_not_found",
                        f"No remote docs found for '{library}'.",
                        ids={"library": library},
                    )
                return {"summary": f"{library}: remote docs.", "source": "available", "text": text}
        raise FarmhandError(
            "library_not_found",
            f"'{library}' is neither installed nor in the catalog.",
            ids={"library": library},
        )
