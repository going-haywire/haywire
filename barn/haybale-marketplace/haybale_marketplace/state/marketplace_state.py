"""MarketplaceState — AppState that owns marketplace orchestration.

Wraps haywire.core.marketstall. The UI editor calls methods on this state —
it doesn't know about marketstall internals directly. Dependencies are
resolved from the ambient DI context in on_enable, mirroring HaystackState's
pattern.

Per spec §3.1: file paths use the future haybale-marketplace subdirectory
(`~/.haywire/db/haybale-marketplace/`). The runtime code lives in
haywire.core.marketstall until the carve-out happens (out of scope here).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from haywire.core.marketstall import (
    Haybale,
    MalformedMarketplaceError,
    MarketplaceFile,
    RefreshReport,
    parse_global_marketplace,
    parse_project_marketplace,
    refresh as runtime_refresh,
    remove_stale_haybale_from_project,
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
      - global_path = ~/.haywire/db/haybale-marketplace/marketplace.toml
        (per spec §3.1; placeholder for the future haybale-marketplace library).
      - project_path = <workspace_root>/.haywire/marketplace.toml.
    """

    def __init__(self) -> None:
        super().__init__()
        self._workspace_root: Optional[Path] = None
        self.last_report: Optional[RefreshReport] = None
        self.global_marketplace_error: Optional[str] = None

    def on_enable(self) -> None:
        from haywire.core.di.context import get_workspace_root

        self._workspace_root = get_workspace_root()

    def on_disable(self) -> None:
        self.last_report = None
        self.global_marketplace_error = None

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _global_path(self) -> Path:
        """~/.haywire/db/haybale-marketplace/marketplace.toml — spec §3.1.

        The `db/haybale-marketplace/` subdirectory is chosen now so the future
        haybale-marketplace carve-out doesn't require a migration. See spec §17
        for the non-goal "carve-out of haybale-marketplace as a separate library
        in this spec."
        """
        return Path.home() / ".haywire" / "db" / "haybale-marketplace" / "marketplace.toml"

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

    def remove_stale_haybale(self, name: str) -> bool:
        """Remove a stale entry from the project [[caches]]. Returns True iff removed."""
        project_path = self._project_path()
        if project_path is None:
            return False
        return remove_stale_haybale_from_project(project_path, name=name)
