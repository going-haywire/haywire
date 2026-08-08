from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from haywire.core.marketstall import (
    FetchedSources,
    Haybale,
    MalformedMarketplaceError,
    MarketplaceFile,
    RefreshReport,
    ResolvedCatalog,
    apply_refresh as runtime_apply,
    fetch_sources as runtime_fetch_sources,
    parse_global_marketplace,
    parse_project_marketplace,
    refresh as runtime_refresh,
    remove_stale_haybale_from_project,
    resolve_catalog as runtime_resolve,
)
from haywire.core.state.base import AppState
from haywire.core.state.decorator import state

logger = logging.getLogger(__name__)


@state(label="Marketplace State")
class MarketplaceState(AppState):
    """Owns marketplace orchestration for the studio library.

    Read API:
      - get_global(): MarketplaceFile | None (None when malformed; sets
        global_marketplace_error so the UI can render the Edit File banner).
      - get_project_haybales(): list[Haybale] from the project [[caches]].

    Orchestration API:
      - refresh(): RefreshReport, runs the refresh pipeline and caches the
        report on self.last_report for the UI to display.

    Path derivation (in on_enable):
      - workspace_root from haywire.core.di.context.get_workspace_root().
      - global_path = ~/.haywire/db/haybale_marketplace/marketplace.toml.
      - project_path = <workspace_root>/.haywire/marketplace.toml.
    """

    def __init__(self) -> None:
        super().__init__()
        self._workspace_root: Optional[Path] = None
        self.last_report: Optional[RefreshReport] = None
        self.global_marketplace_error: Optional[str] = None

    def on_enable(self) -> None:
        from haywire.core.di.context import get_workspace_root

        from haybale_marketplace.config import ensure_marketplace_config

        ensure_marketplace_config()
        self._workspace_root = get_workspace_root()
        self._auto_refresh_if_empty()

    def on_disable(self) -> None:
        self.last_report = None
        self.global_marketplace_error = None

    def _auto_refresh_if_empty(self) -> None:
        """Refresh on first enable when subscriptions exist but caches are empty.

        Covers the fresh-init case: init pre-seeds the global [[markets]] entry
        but the project [[caches]] starts empty, so the library list would be
        blank until the user manually pressed Refresh.
        """
        try:
            global_mf = parse_global_marketplace(self._global_path())
        except MalformedMarketplaceError:
            return
        has_subscriptions = bool(global_mf.markets or global_mf.stalls or global_mf.haybales)
        if not has_subscriptions:
            return
        project_path = self._project_path()
        if project_path is None:
            return
        pm = parse_project_marketplace(project_path)
        if pm.caches:
            return
        try:
            self.refresh()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _global_path(self) -> Path:
        """Path to ~/.haywire/db/haybale_marketplace/marketplace.toml."""
        from haybale_marketplace.config import GLOBAL_MARKETPLACE_DIR

        return GLOBAL_MARKETPLACE_DIR / "marketplace.toml"

    def _project_path(self) -> Optional[Path]:
        if self._workspace_root is None:
            return None
        return self._workspace_root / ".haywire" / "marketplace.toml"

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_global(self) -> Optional[MarketplaceFile]:
        """Parse the global marketplace file. None on malformed.

        On MalformedMarketplaceError, sets self.global_marketplace_error so the
        UI can render an Edit File banner. The error clears on the next
        successful get_global() call.
        """
        try:
            mf = parse_global_marketplace(self._global_path())
        except MalformedMarketplaceError as exc:
            self.global_marketplace_error = str(exc)
            return None
        self.global_marketplace_error = None
        return mf

    def get_project_haybales(self) -> list[Haybale]:
        """Parse <project>/.haywire/marketplace.toml and return its [[caches]] list."""
        project_path = self._project_path()
        if project_path is None:
            return []
        pm = parse_project_marketplace(project_path)
        return list(pm.caches)

    # ------------------------------------------------------------------
    # Orchestration API
    # ------------------------------------------------------------------

    def refresh(self) -> RefreshReport:
        """Run the refresh pipeline. Caches the result on self.last_report."""
        project_path = self._project_path()
        if project_path is None:
            self.last_report = RefreshReport()
            return self.last_report

        report = runtime_refresh(
            global_path=self._global_path(),
            project_path=project_path,
        )
        self.last_report = report
        return report

    # ------------------------------------------------------------------
    # Phased refresh — the same pipeline, stopped between phases
    # ------------------------------------------------------------------
    #
    # A UI that wants to show the user what a refresh would do before writing
    # anything drives these three in order. Only apply_refresh() mutates, so a
    # flow abandoned before it leaves the project file untouched.

    def fetch_sources(self) -> Optional[FetchedSources]:
        """Phase 1 — fetch every subscription. Blocking: call in a thread.

        None when there is no project path, mirroring refresh()'s empty-report
        posture for a workspace-less session.
        """
        project_path = self._project_path()
        if project_path is None:
            return None
        return runtime_fetch_sources(
            global_path=self._global_path(),
            project_path=project_path,
        )

    def resolve(self, fetched: FetchedSources) -> ResolvedCatalog:
        """Phase 2 — pure; safe to call on the event loop."""
        return runtime_resolve(fetched)

    def apply_refresh(self, fetched: FetchedSources, resolved: ResolvedCatalog) -> RefreshReport:
        """Phase 3 — write the project file. Caches the report like refresh()."""
        project_path = self._project_path()
        if project_path is None:
            self.last_report = RefreshReport()
            return self.last_report
        report = runtime_apply(fetched, resolved, project_path=project_path)
        self.last_report = report
        return report

    def remove_stale_haybale(self, name: str) -> bool:
        """Remove a stale entry from the project [[caches]]. Returns True iff removed."""
        project_path = self._project_path()
        if project_path is None:
            return False
        return remove_stale_haybale_from_project(project_path, name=name)

    # ------------------------------------------------------------------
    # Overview fetch (async)
    # ------------------------------------------------------------------

    async def fetch_overview(self, pkg: Haybale, *, cache_dir: "Path | None" = None) -> "str | None":
        """Fetch OVERVIEW.md (or README fallback) for a marketplace-only package.

        Priority:
        1. ``docs_path`` — a path from the repo's git root, resolved against
           ``origin`` at ``install_spec``'s ref. A local path is read from
           disk; otherwise the raw URL is fetched, appending OVERVIEW.md and
           QUICKREF.md in order when the path names a directory.
        2. PyPI long_description fallback — only when step 1 yielded nothing
           and ``source == 'pypi'``.

        There is no branch-guessing heuristic any more. The previous one tried
        ``main`` then ``master`` against a URL derived from ``source_url``,
        which meant a repo using neither silently produced 404s; the ref now
        comes from ``install_spec``, or resolution returns None.

        All remote fetches go through the shared ``fetch_doc`` cache, keyed by
        ``pkg.name``, so a doc body survives a later offline lookup.
        """
        import asyncio
        import json
        from pathlib import Path

        from haywire.core.marketstall.cache import fetch_doc
        from haywire.core.marketstall.locate import resolve_row_path

        def _first_reachable(urls: list) -> "str | None":
            for url in urls:
                body = fetch_doc(url, pkg.name, cache_dir=cache_dir)
                if body:
                    return body
            return None

        # ── 1. Resolve docs_path against the row's origin + ref ──────────────
        if pkg.docs_path:
            local = Path(pkg.docs_path)
            if local.is_dir():
                for candidate in (local / "OVERVIEW.md", local / "QUICKREF.md"):
                    if candidate.exists():
                        return candidate.read_text()
            elif local.is_file():
                return local.read_text()
            else:
                base = resolve_row_path(pkg, pkg.docs_path, form="raw")
                if base:
                    if base.endswith(".md"):
                        candidates = [base]
                    else:
                        stem = base.rstrip("/")
                        candidates = [f"{stem}/OVERVIEW.md", f"{stem}/QUICKREF.md"]
                    content = await asyncio.to_thread(_first_reachable, candidates)
                    if content:
                        return content

        # ── 2. PyPI long_description fallback ────────────────────────────────
        if pkg.source == "pypi":
            url = f"https://pypi.org/pypi/{pkg.name}/json"
            body = await asyncio.to_thread(fetch_doc, url, pkg.name, cache_dir=cache_dir)
            if body:
                try:
                    return json.loads(body).get("info", {}).get("description") or None
                except Exception:
                    return None

        return None
