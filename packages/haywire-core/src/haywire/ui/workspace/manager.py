# packages/haywire-core/src/haywire/ui/workspace/manager.py
"""
WorkspaceManager for managing workspace presets in the Haywire UI system.
"""

from dataclasses import asdict
from typing import Dict, Optional, List
import json
import logging
from pathlib import Path

from haywire.ui.workspace.workspace_state import (
    WorkspaceState,
    AreaState,
    MiddleAreaState,
    TabState,
    _K_GRAPH_EDITOR,
    _K_LIBRARY_BROWSER,
    _K_LIBRARY_DETAIL,
    _K_PROPERTIES,
    _K_CONSOLE,
    _K_FILE_VIEWER,
)

logger = logging.getLogger(__name__)

class WorkspaceManager:
    """
    Manages workspace presets.

    Handles creating, saving, loading, and switching workspaces.
    Each session has its own WorkspaceManager instance with its
    own active workspace, but the saved presets are shared (stored
    in the project folder).

    Default workspaces shipped with Haywire:
        - "Graph Editing": Graph in middle, Properties on right, Library on left

    Attributes:
        active: The currently active WorkspaceState.
        presets: Dict of saved workspace presets by name.
    """

    DEFAULT_PRESETS: Dict[str, WorkspaceState] = {
        "Graph Editing": WorkspaceState(
            name="Graph Editing",
            left_bar_active=_K_LIBRARY_BROWSER,
            left=AreaState(editor_key=_K_LIBRARY_BROWSER, visible=True, size=250),
            middle=MiddleAreaState(
                tabs=[
                    TabState(editor_key=_K_GRAPH_EDITOR, label="Graph"),
                    TabState(editor_key=_K_LIBRARY_DETAIL, label="Library"),
                    TabState(editor_key=_K_FILE_VIEWER, label="File"),
                ],
                active_tab_index=0,
                bottom_visible=False,
            ),
            right_bar_active=_K_PROPERTIES,
            right=AreaState(editor_key=_K_PROPERTIES, visible=True, size=350),
        ),
        "Development": WorkspaceState(
            name="Development",
            left_bar_active=_K_LIBRARY_BROWSER,
            left=AreaState(editor_key=_K_LIBRARY_BROWSER, visible=True, size=250),
            middle=MiddleAreaState(
                tabs=[
                    TabState(editor_key=_K_GRAPH_EDITOR, label="Graph"),
                    TabState(editor_key=_K_LIBRARY_DETAIL, label="Library"),
                    TabState(editor_key=_K_FILE_VIEWER, label="File"),
                ],
                active_tab_index=0,
                bottom_visible=True,
                bottom_size=200,
                bottom_editor_key=_K_CONSOLE,
            ),
            right_bar_active=_K_PROPERTIES,
            right=AreaState(editor_key=_K_PROPERTIES, visible=True, size=350),
        ),
        "Debugging": WorkspaceState(
            name="Debugging",
            left_bar_active=_K_LIBRARY_BROWSER,
            left=AreaState(editor_key=_K_LIBRARY_BROWSER, visible=False, size=250),
            middle=MiddleAreaState(
                tabs=[
                    TabState(editor_key=_K_GRAPH_EDITOR, label="Graph"),
                    TabState(editor_key=_K_LIBRARY_DETAIL, label="Library"),
                    TabState(editor_key=_K_FILE_VIEWER, label="File"),
                ],
                active_tab_index=0,
                bottom_visible=True,
                bottom_size=300,
                bottom_editor_key=_K_CONSOLE,
            ),
            right_bar_active=_K_PROPERTIES,
            right=AreaState(editor_key=_K_PROPERTIES, visible=True, size=350),
        ),
    }

    def __init__(self, project_path: Optional[Path] = None):
        self._project_path = project_path
        self.presets: Dict[str, WorkspaceState] = dict(self.DEFAULT_PRESETS)
        self.active: WorkspaceState = self.presets["Graph Editing"]

        if project_path:
            self._load_user_presets(project_path)

    def switch(self, name: str) -> WorkspaceState:
        """Switch to a named workspace preset.

        Args:
            name: Name of the preset to switch to.

        Returns:
            The newly active WorkspaceState.

        Raises:
            KeyError: If the named preset does not exist.
        """
        if name not in self.presets:
            raise KeyError(f"Workspace '{name}' not found")
        self.active = self.presets[name]
        logger.info(f"WorkspaceManager: Switched to workspace '{name}'")
        return self.active

    def save_current(self, name: Optional[str] = None) -> None:
        """Save the current workspace state as a preset.

        Args:
            name: Name to save under. Defaults to active.name.
        """
        save_name = name or self.active.name
        self.active.name = save_name
        self.presets[save_name] = self.active
        if self._project_path:
            self._persist_presets()

    def get_preset_names(self) -> List[str]:
        """Return list of all preset names."""
        return list(self.presets.keys())

    @staticmethod
    def _deserialize_workspace(state_dict: dict) -> WorkspaceState:
        """Reconstruct a WorkspaceState from a plain dict (from JSON)."""
        left_d = state_dict.get("left", {})
        right_d = state_dict.get("right", {})
        middle_d = state_dict.get("middle", {})
        tabs_data = middle_d.get("tabs", [])
        tabs = [TabState(**t) for t in tabs_data] if tabs_data else [TabState()]
        middle = MiddleAreaState(
            tabs=tabs,
            active_tab_index=middle_d.get("active_tab_index", 0),
            bottom_visible=middle_d.get("bottom_visible", False),
            bottom_size=middle_d.get("bottom_size", 200),
            bottom_editor_key=middle_d.get("bottom_editor_key", "console"),
        )
        return WorkspaceState(
            name=state_dict.get("name", "Unnamed"),
            left_bar_active=state_dict.get("left_bar_active"),
            left=AreaState(**left_d) if left_d else AreaState(),
            middle=middle,
            right_bar_active=state_dict.get("right_bar_active"),
            right=AreaState(**right_d) if right_d else AreaState(),
        )

    def _load_user_presets(self, project_path: Path) -> None:
        """Load saved workspace presets from project .haywire/ folder."""
        preset_file = project_path / ".haywire" / "workspaces.json"
        if preset_file.exists():
            try:
                data = json.loads(preset_file.read_text())
                for name, state_dict in data.items():
                    self.presets[name] = self._deserialize_workspace(state_dict)
            except Exception as e:
                logger.warning(f"WorkspaceManager: Failed to load workspace presets: {e}")

    def _persist_presets(self) -> None:
        """Save workspace presets to project .haywire/ folder."""
        if not self._project_path:
            return
        preset_dir = self._project_path / ".haywire"
        preset_dir.mkdir(parents=True, exist_ok=True)
        preset_file = preset_dir / "workspaces.json"
        data = {}
        for name, ws in self.presets.items():
            data[name] = asdict(ws)
        preset_file.write_text(json.dumps(data, indent=2))
        logger.info(f"WorkspaceManager: Persisted presets to {preset_file}")
