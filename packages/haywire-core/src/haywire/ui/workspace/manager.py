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
    SlotState,
    MainSlotState,
    BottomSlotState,
    TabState,
)

if TYPE_CHECKING:
    from haywire.ui.editor.registry import EditorTypeRegistry

logger = logging.getLogger(__name__)

_STATE_FILENAME = "workspace_state.json"


class WorkspaceManager:
    """
    Manages a single workspace layout per project.

    There are no named presets. The project has one ``WorkspaceState`` persisted
    to ``.haywire/workspace_state.json``. On construction the manager tries to
    load that file; if it is missing or fails to parse, the layout is
    auto-populated from the editor registry (one tab per main-slot editor,
    one tab per bottom-slot editor).

    The bottom slot's tab list is always freshly auto-populated from the
    registry on every load — only the active tab key, visibility, and last
    dragged size survive across sessions. This keeps the bottom tab roster
    in sync with installed editors without requiring users to reset their
    workspace.

    Saving is explicit: callers invoke ``save()`` to write the current
    ``active`` state to disk. Unsaved changes are lost when the session ends.

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
        # Main tabs are a merge of registry-derived `required` tabs and
        # persisted payload-carrying tabs. After load, reconcile both.
        self._refresh_main_tabs(self.active, editor_registry)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist the current active workspace state to disk.

        Two kinds of data are stripped before serialization:

        * The bottom slot's tab list — always re-derived from the editor
          registry on load so newly-installed bottom editors appear in
          existing sessions.
        * Main-slot tabs without a payload — these are ``required`` /
          ``on_context`` singletons that are re-derived (required) or
          re-triggered (on_context) on load; persisting them would
          prevent new ``required`` editors from showing up and would
          resurrect closed ``on_context`` tabs.
        """
        preset_dir = self._project_path / ".haywire"
        preset_dir.mkdir(parents=True, exist_ok=True)
        state_file = preset_dir / _STATE_FILENAME
        payload = asdict(self.active)
        # Drop the runtime-only bottom tab list.
        if "bottom" in payload and isinstance(payload["bottom"], dict):
            payload["bottom"].pop("tabs", None)
        # Drop payload-less main tabs — they are re-derived from the
        # registry / retrigger flow on load.
        if "main" in payload and isinstance(payload["main"], dict):
            main_tabs = payload["main"].get("tabs", [])
            payload["main"]["tabs"] = [
                t
                for t in main_tabs
                if isinstance(t, dict) and t.get("metadata", {}).get("payload") is not None
            ]
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

        The bottom slot's ``tabs`` are left empty — they are re-derived from
        the editor registry in :meth:`_refresh_bottom_tabs` after load.

        This is a strict reader: it only understands the current schema. Old
        ``middle``/``canvas_area`` files will raise and fall back to
        auto-populate via :meth:`_load`'s exception handler.
        """
        left_d = state_dict.get("left", {})
        right_d = state_dict.get("right", {})
        main_d = state_dict["main"]
        bottom_d = state_dict["bottom"]

        tabs_data = main_d.get("tabs", [])
        tabs = [TabState(**t) for t in tabs_data] if tabs_data else [TabState()]
        main = MainSlotState(
            tabs=tabs,
            active_tab_key=main_d.get("active_tab_key"),
        )

        bottom = BottomSlotState(
            active_tab_key=bottom_d.get("active_tab_key"),
            visible=bottom_d.get("visible", False),
            size=bottom_d.get("size", 200),
        )

        return WorkspaceState(
            name=state_dict.get("name", "default"),
            haystack=state_dict.get("haystack"),
            left=SlotState(**left_d) if left_d else SlotState(),
            right=SlotState(**right_d) if right_d else SlotState(),
            main=main,
            bottom=bottom,
        )

    # ------------------------------------------------------------------
    # Auto-populate
    # ------------------------------------------------------------------

    @staticmethod
    def _auto_populate(editor_registry: "EditorTypeRegistry") -> WorkspaceState:
        """Build a fresh WorkspaceState from whatever editors are registered.

        The layout rule is: for each slot, look up every editor whose
        ``default_slot`` matches. The main slot gets one tab per main-slot
        editor whose ``opens`` value is ``REQUIRED`` — editors declared
        ``on_context`` or ``on_payload`` materialize only when triggered.
        The bottom slot is hidden by default; its tab list is populated
        separately by :meth:`_refresh_bottom_tabs`.
        """
        from haywire.ui.editor.identity import OpenBehavior

        left_editors = editor_registry.get_by_default_slot("left")
        right_editors = editor_registry.get_by_default_slot("right")
        main_editors_all = editor_registry.get_by_default_slot("main")
        main_editors = {
            key: cls
            for key, cls in main_editors_all.items()
            if cls.class_identity.opens is OpenBehavior.REQUIRED
        }

        left_first = next(iter(left_editors), None)
        right_first = next(iter(right_editors), None)

        if main_editors:
            tabs = [
                TabState(editor_key=key, label=cls.class_identity.label) for key, cls in main_editors.items()
            ]
        else:
            tabs = [TabState()]

        main_first = tabs[0].editor_key

        return WorkspaceState(
            name="default",
            left=SlotState(active_tab_key=left_first, visible=left_first is not None, size=250),
            right=SlotState(active_tab_key=right_first, visible=right_first is not None, size=350),
            main=MainSlotState(
                tabs=tabs,
                active_tab_key=main_first,
            ),
            bottom=BottomSlotState(),
        )

    # ------------------------------------------------------------------
    # Bottom-tab refresh
    # ------------------------------------------------------------------

    @staticmethod
    def _refresh_bottom_tabs(
        workspace: WorkspaceState,
        editor_registry: "EditorTypeRegistry",
    ) -> None:
        """Re-derive the bottom slot's tab list from the editor registry.

        Called after load and auto-populate so that the bottom tab roster
        always reflects currently-installed editors. The persisted
        ``active_tab_key`` is preserved if the referenced editor still
        exists; otherwise it falls back to the first tab.
        """
        bottom_editors = editor_registry.get_by_default_slot("bottom")
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

    # ------------------------------------------------------------------
    # Main-tab refresh
    # ------------------------------------------------------------------

    @staticmethod
    def _refresh_main_tabs(
        workspace: WorkspaceState,
        editor_registry: "EditorTypeRegistry",
    ) -> None:
        """Reconcile main tab list against the current editor registry.

        Rules:
          * Drop persisted tabs whose ``editor_key`` is unknown to the
            registry (editor class was uninstalled).
          * Drop persisted tabs whose editor is no longer ``on_payload``
            (semantic changed — shouldn't be a payload-carrying tab).
          * Ensure every ``opens=REQUIRED`` main editor has a tab. Inject
            one at the head of the list if missing. Idempotent.
          * Resolve ``active_tab_key`` against the reconciled list; fall
            back to the first tab if the persisted key is no longer
            present.
        """
        from haywire.ui.editor.identity import OpenBehavior

        main_editors = editor_registry.get_by_default_slot("main")

        def _keep(tab: TabState) -> bool:
            if tab.editor_key is None:
                # Placeholder from empty-registry path — keep if nothing else.
                return True
            cls = main_editors.get(tab.editor_key)
            if cls is None:
                # Editor no longer registered — drop the tab.
                return False
            opens = getattr(cls.class_identity, "opens", OpenBehavior.REQUIRED)
            if tab.payload is not None and opens is OpenBehavior.ON_CONTEXT:
                # ON_CONTEXT editors are triggered by context, not by payload —
                # a persisted payload tab for an ON_CONTEXT editor is stale.
                return False
            return True

        kept = [t for t in workspace.main.tabs if _keep(t)]

        # Collect required editors and determine which need injecting.
        required_editors = {
            key: cls
            for key, cls in main_editors.items()
            if cls.class_identity.opens is OpenBehavior.REQUIRED
        }
        # Drop the lone placeholder when real required editors exist.
        if required_editors:
            kept = [t for t in kept if t.editor_key is not None]

        existing_required_keys = {t.editor_key for t in kept if t.payload is None}
        injected: list[TabState] = []
        for key, cls in required_editors.items():
            if key not in existing_required_keys:
                injected.append(TabState(editor_key=key, label=cls.class_identity.label))
        workspace.main.tabs = injected + kept

        if not workspace.main.tabs:
            workspace.main.tabs = [TabState()]

        valid_ids = {t.tab_id for t in workspace.main.tabs if t.editor_key is not None}
        if workspace.main.active_tab_key not in valid_ids:
            workspace.main.active_tab_key = workspace.main.tabs[0].tab_id if workspace.main.tabs else None
