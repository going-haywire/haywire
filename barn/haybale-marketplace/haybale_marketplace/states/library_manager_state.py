"""LibraryManagerState — AppState that publishes the LibraryManager.

Composition over inheritance: the manager is a plain class; this AppState
exists purely as the publishing vehicle so other libraries' editors can
reach the manager via ``ctx.app_data[LibraryManagerState].manager.X``.

Dependencies (registry, workspace root) are resolved from the ambient DI
context in ``on_enable``, mirroring the pattern HaystackState and
MarketplaceState already use.
"""

from __future__ import annotations

import logging
from pathlib import Path

from haybale_marketplace.library_manager import LibraryManager
from haywire.api.workbench import AppState, state

logger = logging.getLogger(__name__)


@state(label="Library Manager State", description="Publishes the LibraryManager for editor consumption.")
class LibraryManagerState(AppState):
    """Publishes the LibraryManager for editor consumption."""

    def __init__(self) -> None:
        super().__init__()
        self.manager: LibraryManager | None = None

    def on_enable(self) -> None:
        from haywire.core.di.config import get_library_system
        from haywire.core.di.context import get_workspace_root

        registry = get_library_system().get_library_registry()
        try:
            workspace_root: Path | None = get_workspace_root()
        except RuntimeError:
            workspace_root = None
        self.manager = LibraryManager(
            registry,
            project_dir=str(workspace_root) if workspace_root else None,
            torch_backend=self._torch_backend,
        )

    @staticmethod
    def _torch_backend() -> str:
        from haybale_marketplace.settings.marketplace_settings import MarketplaceSettings

        try:
            return str(MarketplaceSettings().torch_backend)
        except Exception:
            logger.debug("torch_backend unreadable; using auto", exc_info=True)
            return "auto"

    def on_disable(self) -> None:
        self.manager = None
