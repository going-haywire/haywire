"""MarketplaceState — AppState that owns marketplace orchestration.

Wraps haywire.core.marketplace_runtime (Phase 1+2 of Plan E). The UI editor
calls methods on this state — it doesn't know about marketplace_runtime
directly. Dependencies are resolved from the ambient DI context in on_enable,
mirroring HaystackState's pattern.

Per the architectural decision documented in Plan E: LibraryManager remains
unaware of the marketplace runtime. When haybale-marketplace is carved out
of haybale-studio (separate spec T11), this state module moves with the
Library Browser editor.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from haywire.core.marketplace import MarketplaceEntry
from haywire.core.marketplace_errors import MalformedGlobalMarketplaceError
from haywire.core.marketplace_runtime import (
    GlobalMarketplace,
    RefreshReport,
    parse_global_marketplace,
    parse_project_marketplace,
)
from haywire.core.marketplace_runtime import refresh as runtime_refresh
from haywire.core.state.base import AppState
from haywire.core.state.decorator import state

logger = logging.getLogger(__name__)


@state(label="Marketplace State")
class MarketplaceState(AppState):
    """Owns marketplace orchestration for the studio library.

    Read API:
      - get_global(): GlobalMarketplace | None (None when malformed; sets
        global_marketplace_error so the UI can render the Edit File banner).
      - get_project_packages(): list[MarketplaceEntry] from the project cache.

    Orchestration API:
      - refresh(): RefreshReport, runs the 7-step refresh pipeline and
        caches the report on self.last_report for the UI to display.

    Path derivation (in on_enable):
      - workspace_root from haywire.core.di.context.get_workspace_root().
      - global_path = ~/.haywire/marketplace.toml (Path.home() + config).
      - project_path = <workspace_root>/.haywire/marketplace.toml.
    """

    def __init__(self) -> None:
        super().__init__()
        self._workspace_root: Optional[Path] = None
        self.last_report: Optional[RefreshReport] = None
        self.global_marketplace_error: Optional[str] = None

    def on_enable(self) -> None:
        """Resolve ambient dependencies."""
        from haywire.core.di.context import get_workspace_root

        self._workspace_root = get_workspace_root()

    def on_disable(self) -> None:
        """Clear cached state."""
        self.last_report = None
        self.global_marketplace_error = None

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _global_path(self) -> Path:
        """~/.haywire/marketplace.toml via Path.home()."""
        return Path.home() / ".haywire" / "marketplace.toml"

    def _project_path(self) -> Optional[Path]:
        """<workspace_root>/.haywire/marketplace.toml — None if workspace_root unset."""
        if self._workspace_root is None:
            return None
        return self._workspace_root / ".haywire" / "marketplace.toml"

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_global(self) -> Optional[GlobalMarketplace]:
        """Parse ~/.haywire/marketplace.toml. Returns None if malformed.

        On MalformedGlobalMarketplaceError, sets self.global_marketplace_error
        to the message so the UI can render an Edit File banner. The error
        clears on the next successful get_global() call.
        """
        try:
            gm = parse_global_marketplace(self._global_path())
        except MalformedGlobalMarketplaceError as exc:
            self.global_marketplace_error = str(exc)
            logger.warning(f"MarketplaceState: malformed global marketplace: {exc}")
            return None
        self.global_marketplace_error = None
        return gm

    def get_project_packages(self) -> list[MarketplaceEntry]:
        """Return the [[packages]] cache from the project marketplace.

        Empty list when the project has no marketplace.toml yet (e.g.
        before the first refresh) or when workspace_root is unset.
        """
        project_path = self._project_path()
        if project_path is None:
            return []
        pm = parse_project_marketplace(project_path)
        return list(pm.packages)

    # ------------------------------------------------------------------
    # Orchestration API
    # ------------------------------------------------------------------

    def refresh(self) -> RefreshReport:
        """Run the spec §6 refresh and cache the result on self.last_report.

        Returns an empty RefreshReport if workspace_root is unset (caller
        should handle this — usually means the editor is showing without
        an open project).
        """
        project_path = self._project_path()
        if project_path is None:
            empty = RefreshReport()
            self.last_report = empty
            return empty

        report = runtime_refresh(self._global_path(), project_path)
        self.last_report = report
        return report
