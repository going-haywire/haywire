"""LibraryEnableState — runtime user enable/disable toggles, write-through.

The **bootstrap read path** for persisted-disabled-state lives in
``haywire.core.library.disabled_state_io`` and is consulted by the library
system *before* ``enable_all_libraries()``. This AppState handles only the
**runtime write path**: when the user clicks enable/disable in the UI,
the toggle goes through here, the registry is mutated, and the new
disabled list is persisted to ``<project>/.haywire/config.toml``.

Splitting the read/write paths this way avoids a mid-bootstrap mutation
cascade — see ADR-0001 (decision Q6/D).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from haywire.core.library.disabled_state_io import write_disabled_ids
from haywire.core.state.base import AppState
from haywire.core.state.decorator import state

logger = logging.getLogger(__name__)


@state(label="Library Enable State")
class LibraryEnableState(AppState):
    """Owns the runtime write path for persisted-disabled-state."""

    def enable(self, library_id: str) -> None:
        registry = self._registry()
        registry.enable_library(library_id)
        self._persist(registry)

    def disable(self, library_id: str) -> None:
        registry = self._registry()
        registry.disable_library(library_id)
        self._persist(registry)

    @staticmethod
    def _registry():
        from haywire.core.di.config import get_library_system

        return get_library_system().get_library_registry()

    @staticmethod
    def _persist(registry) -> None:
        from haywire.core.di.context import get_workspace_root

        try:
            workspace_root: Optional[Path] = get_workspace_root()
        except RuntimeError:
            return
        if workspace_root is None:
            return
        disabled = [lib_id for lib_id in registry.list_names() if not registry.is_library_enabled(lib_id)]
        write_disabled_ids(workspace_root, disabled)
