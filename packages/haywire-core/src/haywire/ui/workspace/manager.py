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
    BottomAreaState,
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
    one tab per bottom-area editor).

    The bottom-area tab list is always freshly auto-populated from the
    registry on every load — only the active tab key, visibility, and last
    dragged size survive across sessions. This keeps the bottom tab roster
    in sync with installed editors without requiring users to reset their
    workspace.

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

        # Bottom tabs are runtime-only and must always reflect the current
        # registry, so refresh them after both load and auto-populate paths.
        self._refresh_bottom_tabs(self.active, editor_registry)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist the current active workspace state to disk.

        The bottom-area tab list is stripped before serialization — it is
        always re-derived from the editor registry on load.
        """
        preset_dir = self._project_path / ".haywire"
        preset_dir.mkdir(parents=True, exist_ok=True)
        state_file = preset_dir / _STATE_FILENAME
        payload = asdict(self.active)
        # Drop the runtime-only bottom tab list — it will be re-derived from
        # the registry on load, so persisting it would cause new bottom
        # editors to be invisible to existing sessions.
        if "bottom" in payload and isinstance(payload["bottom"], dict):
            payload["bottom"].pop("tabs", None)
        state_file.write_text(json.dumps(payload, indent=2))
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
        """Reconstruct a WorkspaceState from a plain dict (from JSON).

        The bottom area's ``tabs`` are left empty — they are re-derived from
        the editor registry in :meth:`_refresh_bottom_tabs` after load.

        For backwards compatibility, legacy ``middle.bottom_*`` fields from
        the pre-BottomAreaState schema are read and migrated into the new
        top-level ``bottom`` field.
        """
        left_d = state_dict.get("left", {})
        right_d = state_dict.get("right", {})
        middle_d = state_dict.get("middle", {})
        bottom_d = state_dict.get("bottom")

        tabs_data = middle_d.get("tabs", [])
        tabs = [TabState(**t) for t in tabs_data] if tabs_data else [TabState()]
        middle = MiddleAreaState(
            tabs=tabs,
            active_tab_index=middle_d.get("active_tab_index", 0),
        )

        if bottom_d is None:
            # Legacy migration: pre-BottomAreaState schema stored bottom_* fields
            # inside middle. Read them once; a later save() will persist the
            # migrated shape.
            legacy_key = middle_d.get("bottom_editor_key")
            bottom = BottomAreaState(
                active_tab_key=legacy_key,
                visible=middle_d.get("bottom_visible", False),
                size=middle_d.get("bottom_size", 200),
            )
        else:
            bottom = BottomAreaState(
                active_tab_key=bottom_d.get("active_tab_key"),
                visible=bottom_d.get("visible", False),
                size=bottom_d.get("size", 200),
            )

        return WorkspaceState(
            name=state_dict.get("name", "default"),
            left_bar_active=state_dict.get("left_bar_active"),
            left=AreaState(**left_d) if left_d else AreaState(),
            middle=middle,
            bottom=bottom,
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
        ``canvas_area`` matches. The middle area gets one tab per middle-area
        editor. The bottom area is hidden by default; its tab list is
        populated separately by :meth:`_refresh_bottom_tabs`.
        """
        left_editors = editor_registry.get_by_default_area("left")
        right_editors = editor_registry.get_by_default_area("right")
        middle_editors = editor_registry.get_by_default_area("middle")

        left_first = next(iter(left_editors), None)
        right_first = next(iter(right_editors), None)

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
            ),
            bottom=BottomAreaState(),
            right_bar_active=right_first,
            right=AreaState(editor_key=right_first, visible=right_first is not None, size=350),
        )

    # ------------------------------------------------------------------
    # Bottom-tab refresh
    # ------------------------------------------------------------------

    @staticmethod
    def _refresh_bottom_tabs(
        workspace: WorkspaceState,
        editor_registry: "EditorTypeRegistry",
    ) -> None:
        """Re-derive the bottom-area tab list from the editor registry.

        Called after load and auto-populate so that the bottom tab roster
        always reflects currently-installed editors. The persisted
        ``active_tab_key`` is preserved if the referenced editor still
        exists; otherwise it falls back to the first tab.
        """
        bottom_editors = editor_registry.get_by_default_area("bottom")
        workspace.bottom.tabs = [
            TabState(editor_key=key, label=cls.class_identity.label) for key, cls in bottom_editors.items()
        ]

        valid_keys = {t.editor_key for t in workspace.bottom.tabs}
        if workspace.bottom.active_tab_key not in valid_keys:
            # Fall back to the first tab if the previously-active editor is
            # gone (or was never set). None if the registry has no bottom
            # editors at all.
            workspace.bottom.active_tab_key = (
                workspace.bottom.tabs[0].editor_key if workspace.bottom.tabs else None
            )
