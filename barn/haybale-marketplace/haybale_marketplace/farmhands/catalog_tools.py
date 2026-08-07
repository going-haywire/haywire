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
    truncation_note,
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
        raise FarmhandError(
            "marketplace_unavailable",
            "LibraryManager is not initialized on this studio.",
            help="Run studio_status to check the studio's state; the marketplace may still be starting.",
        )
    return manager


def _progress_cb(ctx: FarmhandContext):
    """Bridge LibraryManager's sync on_output callback to async ctx.progress."""
    loop = asyncio.get_running_loop()

    def on_output(line: str) -> None:
        loop.create_task(ctx.progress(line))

    return on_output


_HAYBALE_BASE_FIELDS = ("name", "version", "label", "install_spec")
"""Default row: enough to decide what to install, nothing more. `asdict()` on a
Haybale emits 21 fields of which most are empty on a typical catalog — those
paid full token cost per row for no information. The rest is one `detail=true`
away."""

_HAYBALE_RUNTIME_ONLY = ("source_label", "source_file", "source_origin")
"""Routing metadata the cache uses internally (types.py marks it "runtime-only,
not persisted"). Never useful to an agent, so it is dropped even in detail
mode."""


def _haybale_row(haybale, detail: bool) -> dict:
    if not detail:
        return {f: getattr(haybale, f) for f in _HAYBALE_BASE_FIELDS}
    # Detail: everything meaningful, minus runtime-only routing, minus fields
    # that are empty for this row (an absent value says nothing worth a token).
    return {k: v for k, v in asdict(haybale).items() if k not in _HAYBALE_RUNTIME_ONLY and (v or v is False)}


@farmhand(
    label="List available",
    description="Merged AVAILABLE catalog (not-installed libraries) from the marketplace cache. "
    "Returns name/version/label/install_spec per row; pass detail=true for the full record "
    "(description, author, tags, dependencies, source_url, docs_url, ...).",
    registry_id="list_available",
    annotations=ToolAnnotations(read_only_hint=True),
)
class MarketplaceListAvailableTool(Farmhand):
    async def run(
        self, ctx: FarmhandContext, limit: int = 50, offset: int = 0, detail: bool = False
    ) -> dict:
        haybales = _marketplace_state(ctx).get_project_haybales()
        total = len(haybales)
        rows = [_haybale_row(h, detail) for h in haybales[offset : offset + limit]]
        summary = f"{total} haybales available.{truncation_note(len(rows), total, offset)}"
        result = {"summary": summary, "haybales": rows, "total": total}
        if rows:
            result["help"] = (
                "Run marketplace_get_library_docs library=<name> to read a haybale's docs, "
                "marketplace_dry_run_install install_spec=<install_spec> to preview an install"
                + ("" if detail else ", or re-run with detail=true for full records")
                + "."
            )
        return result


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


_DOC_CHAR_CAP = 12000
"""Characters of doc text returned by default. OVERVIEW/QUICKREF files are
usually well under this; a long README would otherwise dominate the caller's
context with no signal that it did."""


def _doc_result(summary: str, text: str, full: bool, **extra: object) -> dict:
    """Shared shape for every docs return: truncate unless full=, and when
    truncated say by how much and how to get the rest."""
    total = len(text)
    if full or total <= _DOC_CHAR_CAP:
        return {"summary": summary, "text": text, "total_chars": total, **extra}
    return {
        "summary": f"{summary} (showing first {_DOC_CHAR_CAP} of {total} chars)",
        "text": text[:_DOC_CHAR_CAP],
        "total_chars": total,
        "truncated": True,
        "help": "Re-run with full=true for the complete document.",
        **extra,
    }


@farmhand(
    label="Get library docs",
    description="Docs for an installed library (OVERVIEW/QUICKREF/README from its folder) or an "
    "available one (network fetch of its docs_url). Pass component=<registry_key> to fetch one "
    "component's deep doc (installed: wheel; available: docs_url). Long documents are truncated "
    f"at {_DOC_CHAR_CAP} chars with total_chars reported; pass full=true for everything.",
    registry_id="get_library_docs",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True),
)
class MarketplaceGetLibraryDocsTool(Farmhand):
    async def run(self, ctx: FarmhandContext, library: str, component: str = "", full: bool = False) -> dict:
        from haywire.core.library.kinds import doc_filename

        registry = ctx.registry(LibraryRegistry)
        installed = library in registry.list_names()

        if component:
            rel = f"docs/{doc_filename(component)}"
            if installed:
                folder = Path(registry.get_library_identity(library).folder_path)
                path = folder / rel
                if path.exists():
                    return _doc_result(
                        f"{component}: component doc ({path.stat().st_size} bytes).",
                        path.read_text(encoding="utf-8"),
                        full,
                        source="installed",
                        registry_key=component,
                    )
                raise FarmhandError(
                    "docs_not_found",
                    f"No generated doc for '{component}' in installed '{library}'.",
                    ids={"library": library, "component": component},
                    help=(
                        f"Run studio_describe_component registry_key={component!r} for its "
                        f"identity and docstring, or omit component= for the library's docs."
                    ),
                )
            from haywire.core.marketstall.cache import fetch_doc

            for pkg in _marketplace_state(ctx).get_project_haybales():
                if pkg.name == library and pkg.docs_url:
                    url = pkg.docs_url.rstrip("/") + "/" + rel
                    text = await asyncio.to_thread(fetch_doc, url, pkg.name)
                    if text:
                        return _doc_result(
                            f"{component}: remote component doc.",
                            text,
                            full,
                            source="available",
                            registry_key=component,
                        )
            raise FarmhandError(
                "docs_not_found",
                f"No remote doc for '{component}' under '{library}'.",
                ids={"library": library, "component": component},
            )

        if installed:
            folder = Path(registry.get_library_identity(library).folder_path)
            for name in _DOC_FILES:
                path = folder / name
                if path.exists():
                    return _doc_result(
                        f"{library}: {name} ({path.stat().st_size} bytes).",
                        path.read_text(encoding="utf-8"),
                        full,
                        source="installed",
                        file=name,
                    )
            raise FarmhandError(
                "docs_not_found",
                f"'{library}' ships no OVERVIEW/QUICKREF/README.",
                ids={"library": library},
                help=(
                    f"Run studio_list_components library={library!r} to survey what it provides, "
                    f"then studio_describe_component for a specific one."
                ),
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
                return _doc_result(f"{library}: remote docs.", text, full, source="available")
        raise FarmhandError(
            "library_not_found",
            f"'{library}' is neither installed nor in the catalog.",
            ids={"library": library},
            help=(
                "Run studio_list_libraries for installed libraries, marketplace_list_available "
                "for the catalog, or marketplace_refresh if the catalog looks stale."
            ),
        )
