# packages/haywire-core/src/haywire/ui/workspace/manager.py
"""
WorkspaceManager for managing the single persisted workspace layout.
"""

from dataclasses import asdict
from typing import Optional, TYPE_CHECKING
import json
import logging
from pathlib import Path

from haywire.ui.workspace.workspace_state import (
    WorkspaceState,
    AreaState,
    MiddleAreaState,
    TabState,
)

if TYPE_CHECKING:
    from haywire.ui.editor.registry import EditorTypeRegistry

logger = logging.getLogger(__name__)

_STATE_FILENAME = "workspace_state.json"


class WorkspaceManager:
    """
    Manages a single workspace layout per project.

    There are no named presets. The project has one `WorkspaceState` persisted
    to `.haywire/workspace_state.json`. On construction the manager tries to
    load that file; if it is missing or fails to parse, the layout is
    auto-populated from the editor registry (one tab per middle-area editor,
    the first left/right/bottom editor docked into its respective area).

    Saving is explicit: callers invoke `save()` to write the current `active`
    state to disk. Unsaved changes are lost when the session ends.

    Attributes:
        active: The current WorkspaceState.
    """

    def __init__(
        self,
        project_path: Path,
        editor_registry: "EditorTypeRegistry",
    ):
        self._project_path = project_path
        self._editor_registry = editor_registry

        loaded = self._load()
        if loaded is not None:
            self.active = loaded
        else:
            self.active = self._auto_populate(editor_registry)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist the current active workspace state to disk."""
        preset_dir = self._project_path / ".haywire"
        preset_dir.mkdir(parents=True, exist_ok=True)
        state_file = preset_dir / _STATE_FILENAME
        state_file.write_text(json.dumps(asdict(self.active), indent=2))
        logger.info(f"WorkspaceManager: Persisted workspace state to {state_file}")

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self) -> Optional[WorkspaceState]:
        """Load workspace state from the project .haywire/ folder.

        Returns the deserialized WorkspaceState, or None if the file is
        missing or fails to parse.
        """
        state_file = self._project_path / ".haywire" / _STATE_FILENAME
        if not state_file.exists():
            return None
        try:
            data = json.loads(state_file.read_text())
            return self._deserialize_workspace(data)
        except Exception as e:
            logger.warning(
                f"WorkspaceManager: Failed to load workspace state from {state_file}: {e}. "
                "Falling back to auto-populate."
            )
            return None

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
            bottom_editor_key=middle_d.get("bottom_editor_key", None),
        )
        return WorkspaceState(
            name=state_dict.get("name", "default"),
            left_bar_active=state_dict.get("left_bar_active"),
            left=AreaState(**left_d) if left_d else AreaState(),
            middle=middle,
            right_bar_active=state_dict.get("right_bar_active"),
            right=AreaState(**right_d) if right_d else AreaState(),
        )

    # ------------------------------------------------------------------
    # Auto-populate
    # ------------------------------------------------------------------

    @staticmethod
    def _auto_populate(editor_registry: "EditorTypeRegistry") -> WorkspaceState:
        """Build a fresh WorkspaceState from whatever editors are registered.

        The layout rule is: for each area, look up every editor whose
        `default_area` matches, and dock the first one found. The middle area
        gets one tab per middle-area editor. The bottom area is hidden by
        default even if a bottom editor is registered.
        """
        left_editors = editor_registry.get_by_default_area("left")
        right_editors = editor_registry.get_by_default_area("right")
        middle_editors = editor_registry.get_by_default_area("middle")
        bottom_editors = editor_registry.get_by_default_area("bottom")

        left_first = next(iter(left_editors), None)
        right_first = next(iter(right_editors), None)
        bottom_first = next(iter(bottom_editors), None)

        if middle_editors:
            tabs = [
                TabState(editor_key=key, label=cls.class_identity.label)
                for key, cls in middle_editors.items()
            ]
        else:
            tabs = [TabState()]

        return WorkspaceState(
            name="default",
            left_bar_active=left_first,
            left=AreaState(editor_key=left_first, visible=left_first is not None, size=250),
            middle=MiddleAreaState(
                tabs=tabs,
                active_tab_index=0,
                bottom_visible=False,
                bottom_size=200,
                bottom_editor_key=bottom_first,
            ),
            right_bar_active=right_first,
            right=AreaState(editor_key=right_first, visible=right_first is not None, size=350),
        )
