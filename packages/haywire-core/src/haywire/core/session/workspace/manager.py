# packages/haywire-core/src/haywire/ui/workspace/manager.py
"""
WorkspaceManager — dumb JSON persistence for the workspace snapshot.

Holds a raw ``snapshot`` dict. Knows nothing about slots, editors, or
OpenBehavior. Slots are responsible for interpreting and producing snapshots.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_STATE_FILENAME = "workspace_state.json"


class WorkspaceManager:
    """
    Loads and saves the workspace snapshot dict to/from disk.

    The snapshot is a plain dict with one key per slot name plus a
    ``"haystack"`` key. The structure of each slot sub-dict is defined and
    interpreted by the slot classes — WorkspaceManager is intentionally
    unaware of it.

    Attributes:
        snapshot: The raw dict loaded from disk, or ``{}`` if no file exists
            or the file failed to parse. Updated by ``save()``.
    """

    def __init__(self, project_path: Path):
        self._project_path = project_path
        self.snapshot: dict = self._load()

    def _load(self) -> dict:
        """Read the snapshot from disk. Returns ``{}`` on missing or corrupt file."""
        state_file = self._project_path / ".haywire" / _STATE_FILENAME
        if not state_file.exists():
            return {}
        try:
            return json.loads(state_file.read_text())
        except Exception as e:
            logger.warning(f"WorkspaceManager: failed to load {state_file}: {e}. Starting fresh.")
            return {}

    def save(self, snapshot: dict) -> None:
        """Persist ``snapshot`` to disk and update ``self.snapshot``."""
        preset_dir = self._project_path / ".haywire"
        preset_dir.mkdir(parents=True, exist_ok=True)
        state_file = preset_dir / _STATE_FILENAME
        state_file.write_text(json.dumps(snapshot, indent=2))
        self.snapshot = snapshot
        logger.info(f"WorkspaceManager: saved snapshot to {state_file}")
