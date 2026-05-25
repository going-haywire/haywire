"""LibraryManagerState — AppState that publishes the LibraryManager.

Composition over inheritance: the manager is a plain class; this AppState
exists purely as the publishing vehicle so other libraries' editors can
reach the manager via ``ctx.app_data[LibraryManagerState].manager.X``.
See ADR-0001 (decision Q3/C).

Dependencies (registry, workspace root) are resolved from the ambient DI
context in ``on_enable``, mirroring the pattern HaystackState and
MarketplaceState already use.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from haywire.core.state.base import AppState
from haywire.core.state.decorator import state

from haybale_marketplace.library_manager import LibraryManager

logger = logging.getLogger(__name__)


@state(label="Library Manager State")
class LibraryManagerState(AppState):
    """Publishes the LibraryManager for editor consumption."""

    def __init__(self) -> None:
        super().__init__()
        self.manager: Optional[LibraryManager] = None

    def on_enable(self) -> None:
        from haywire.core.di.config import get_library_system
        from haywire.core.di.context import get_workspace_root

        registry = get_library_system().get_library_registry()
        try:
            workspace_root: Optional[Path] = get_workspace_root()
        except RuntimeError:
            workspace_root = None
        self.manager = LibraryManager(
            registry,
            project_dir=str(workspace_root) if workspace_root else None,
        )

    def on_disable(self) -> None:
        self.manager = None
