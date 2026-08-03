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
        1. ``docs_url`` field — explicit raw URL to OVERVIEW.md or to the
           directory that contains it (e.g. a GitHub raw content URL).
           If the URL ends with a filename it is fetched directly; otherwise
           OVERVIEW.md and QUICKREF.md are appended and tried in order.
        2. Heuristic GitHub lookup — derived from ``source_url`` or
           ``install_spec``, for both pypi and git sources. The module name
           is inferred from the package name (``-`` → ``_``) and the optional
           ``#subdirectory=`` fragment of ``install_spec`` is respected.
        3. PyPI long_description fallback — only when no GitHub URL is found
           and ``source == 'pypi'``.

        All remote fetches go through the shared ``fetch_doc`` cache, keyed by
        ``pkg.name``, so a doc body survives a later offline lookup.
        """
        import asyncio
        import json
        from pathlib import Path

        from haywire.core.marketstall.cache import fetch_doc

        def _first_reachable(urls: list) -> "str | None":
            for url in urls:
                body = fetch_doc(url, pkg.name, cache_dir=cache_dir)
                if body:
                    return body
            return None

        # ── 1. Explicit docs_url ──────────────────────────────────────────────
        if pkg.docs_url:
            p = Path(pkg.docs_url)
            if p.is_dir():
                for candidate in (p / "OVERVIEW.md", p / "QUICKREF.md"):
                    if candidate.exists():
                        return candidate.read_text()
            elif p.is_file():
                return p.read_text()
            elif pkg.docs_url.startswith("http"):
                url = pkg.docs_url.rstrip("/")
                if url.endswith(".md"):
                    candidates = [url]
                else:
                    candidates = [f"{url}/OVERVIEW.md", f"{url}/QUICKREF.md"]
                content = await asyncio.to_thread(_first_reachable, candidates)
                if content:
                    return content

        # ── 2. Heuristic: derive raw GitHub URL ──────────────────────────────
        module_name = pkg.name.replace("-", "_")

        subdir = ""
        if pkg.install_spec and "#subdirectory=" in pkg.install_spec:
            subdir = pkg.install_spec.split("#subdirectory=")[-1].strip("/")

        def _github_raw_base(url: str) -> "str | None":
            url = url.rstrip("/").removesuffix(".git")
            if "github.com" not in url:
                return None
            return url.replace("https://github.com/", "https://raw.githubusercontent.com/")

        raw_base = None
        if pkg.source_url and "github.com" in pkg.source_url:
            raw_base = _github_raw_base(pkg.source_url)
        elif pkg.source == "git" and pkg.install_spec:
            git_url = pkg.install_spec.removeprefix("git+").split("@")[0].split("#")[0].rstrip("/")
            raw_base = _github_raw_base(git_url)

        if raw_base:
            candidates = []
            for branch in ("main", "master"):
                prefix = f"{raw_base}/{branch}"
                pkg_prefix = f"{prefix}/{subdir}/{module_name}" if subdir else f"{prefix}/{module_name}"
                candidates.append(f"{pkg_prefix}/OVERVIEW.md")
                candidates.append(f"{pkg_prefix}/QUICKREF.md")
            for branch in ("main", "master"):
                prefix = f"{raw_base}/{branch}"
                if subdir:
                    candidates.append(f"{prefix}/{subdir}/OVERVIEW.md")
                candidates.append(f"{prefix}/OVERVIEW.md")

            content = await asyncio.to_thread(_first_reachable, candidates)
            if content:
                return content

        # ── 3. PyPI long_description fallback ────────────────────────────────
        if pkg.source == "pypi":
            url = f"https://pypi.org/pypi/{pkg.name}/json"
            body = await asyncio.to_thread(fetch_doc, url, pkg.name, cache_dir=cache_dir)
            if body:
                try:
                    return json.loads(body).get("info", {}).get("description") or None
                except Exception:
                    return None

        return None
