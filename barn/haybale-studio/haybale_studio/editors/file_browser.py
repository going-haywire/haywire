"""
LazyFileBrowserEditor — eager-then-lazy project file tree.

Hybrid strategy: walk three levels eagerly (so most navigation is instant),
then plant a "Click to load children" sentinel under any folder that still
has unloaded contents. Clicking the sentinel walks another three levels
from that folder and splices the result back into the tree.

This avoids two pain points:
- The eager browser's hard depth limit (folders past depth 8 are invisible).
- A pure on-expand lazy browser, which trips a q-tree quirk where an
  already-expanded subtree's children don't re-render after a prop update,
  leaving the user staring at a stale Loading… placeholder.

Trade-offs:
- Symlinked directories are treated as leaves (not followed) so we don't
  need explicit cycle bookkeeping.
- Excluded directory names (.git, node_modules, …) never get a sentinel —
  they appear as empty folders, intentionally.
- Refresh re-walks from the workspace root and resets all sentinels.
"""

import copy
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from haywire_studio.app import HaywireApp
from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.context_events import ContextChangeType, ContextChangedEvent

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from nicegui.element import Element


# Suffix appended to a folder path to form the id of its "load more"
# sentinel child. Lets us recognise sentinel clicks in _on_select.
_LOAD_MORE_ID = "__load_more__"

# How many levels each walk pulls in (initial render + each sentinel click).
_BATCH_DEPTH = 3


@editor(
    label="Files",
    icon=hui.icon.folder,
    default_slot="left",
    description=(
        "Project file tree, eager-then-lazy: three levels are loaded up"
        " front, then 'Click to load children' sentinels appear at deeper"
        " folders so the user can pull in three more levels on demand."
    ),
)
class LazyFileBrowserEditor(BaseEditor):
    """File tree that loads three levels at a time on demand."""

    _EXCLUDE_DIRS: frozenset = frozenset(
        {
            "__pycache__",
            ".venv",
            "venv",
            "node_modules",
            "dist",
            "build",
            ".git",
        }
    )
    _GRAPH_EXTS: frozenset = frozenset({".haywire"})

    def __init__(self):
        self._root_path: Optional[Path] = None
        self._tree_container = None
        self._tree: Optional[ui.tree] = None
        # Authoritative node tree. We mutate this freely, then push a
        # deep-copy into the tree's props so Vue/Quasar see fresh
        # references. Indexing always tracks _root_nodes.
        self._root_nodes: list[dict] = []
        # Map node id (filesystem path string) → node dict in _root_nodes,
        # so a sentinel click can find its parent and replace its children.
        self._nodes_by_id: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    # Class-level guard: ui.add_css is page-global and stacking it on every
    # draw() injected duplicate <style> tags AND triggered a Vue mounting
    # race that broke other editors (notably the graph editor's ZoomPan
    # canvas — it ended up sized 0×0 and threw "$refs is undefined" on
    # first run_method). Fire it exactly once per process.
    _CSS_INSTALLED: bool = False

    @classmethod
    def _install_css(cls) -> None:
        if cls._CSS_INSTALLED:
            return
        ui.add_css(
            ".hw-file-tree .q-tree__node-header {"
            " padding-top: 2px; padding-bottom: 3px;"
            " }"
            ".hw-file-tree .q-tree__node-collapsible,"
            ".hw-file-tree .q-tree__node-header {"
            " border-color: var(--hw-border);"
            " }"
        )
        cls._CSS_INSTALLED = True

    def draw(self, context: "SessionContext", container: "Element") -> None:
        app = context.app
        if app and hasattr(app, "workspace_root"):
            self._root_path = Path(app.workspace_root)

        self._install_css()

        with container:
            with ui.column().classes("w-full h-full gap-0"):
                name = self._root_path.name if self._root_path else "No project"
                with hui.panel_header(name, icon=hui.icon.folder_open):
                    hui.icon_action(
                        "refresh", tooltip="Refresh tree", on_click=lambda: self._refresh(context)
                    )

                with ui.scroll_area().classes("flex-1 w-full"):
                    self._tree_container = ui.column().classes("w-full p-1 gap-0")
                    self._render_tree(context)

    def _render_tree(self, context: "SessionContext") -> None:
        if self._tree_container is None:
            return
        self._tree_container.clear()
        self._root_nodes = []
        self._nodes_by_id.clear()

        if self._root_path is None or not self._root_path.exists():
            with self._tree_container:
                ui.label("No project loaded").classes("text-xs hw-text-dim p-2")
            return

        self._root_nodes = self._build_subtree(self._root_path, depth=0)
        if not self._root_nodes:
            with self._tree_container:
                ui.label("Project folder is empty").classes("text-xs hw-text-dim p-2")
            return
        self._index_nodes(self._root_nodes)

        with self._tree_container:
            self._tree = (
                ui.tree(
                    copy.deepcopy(self._root_nodes),
                    label_key="label",
                    node_key="id",
                    on_select=lambda e: self._on_select(e.value, context),
                )
                .props("dense no-transition")
                .classes("w-full text-sm hw-file-tree")
            )

    # ------------------------------------------------------------------
    # filesystem walk
    # ------------------------------------------------------------------

    def _build_subtree(self, path: Path, depth: int) -> list[dict]:
        """Recursively build node dicts up to ``_BATCH_DEPTH`` deep.

        Beyond that, plant a single "Click to load children" sentinel under
        each folder that still has unloaded contents (excluded dirs and
        empty dirs get nothing).
        """
        items: list[dict] = []
        try:
            entries = sorted(
                path.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except (PermissionError, OSError):
            return items
        for entry in entries:
            if entry.name.startswith(".") and entry.name != ".haywire":
                continue
            if entry.is_dir() and entry.name in self._EXCLUDE_DIRS:
                continue
            node: dict = {"id": str(entry), "label": entry.name}
            if entry.is_dir() and not entry.is_symlink():
                if depth + 1 < _BATCH_DEPTH:
                    node["children"] = self._build_subtree(entry, depth + 1)
                else:
                    node["children"] = self._sentinel_for(entry)
            items.append(node)
        return items

    def _sentinel_for(self, path: Path) -> list[dict]:
        """Return a single 'load more' child dict for ``path``, or [] when
        the folder is known to be empty / fully excluded."""
        try:
            for entry in path.iterdir():
                if entry.name.startswith(".") and entry.name != ".haywire":
                    continue
                if entry.is_dir() and entry.name in self._EXCLUDE_DIRS:
                    continue
                return [
                    {
                        "id": f"{path}::{_LOAD_MORE_ID}",
                        "label": "Click to load children",
                    }
                ]
        except (PermissionError, OSError):
            pass
        return []

    def _index_nodes(self, nodes: list[dict]) -> None:
        """Walk a freshly built subtree and register each node by id.

        Sentinels are not indexed — they never become parents, and we
        recognise them by id suffix in _on_select.
        """
        for node in nodes:
            if node["id"].endswith(_LOAD_MORE_ID):
                continue
            self._nodes_by_id[node["id"]] = node
            for child in node.get("children") or []:
                if not child["id"].endswith(_LOAD_MORE_ID):
                    self._index_nodes([child])

    def _expand_sentinel(self, parent_id: str) -> None:
        """Replace the sentinel under ``parent_id`` with three more levels.

        No-op when the sentinel has already been expanded (parent's children
        no longer end with a sentinel).
        """
        node = self._nodes_by_id.get(parent_id)
        if node is None:
            return
        path = Path(parent_id)
        if not path.is_dir():
            return
        children = self._build_subtree(path, depth=0)
        node["children"] = children
        self._index_nodes(children)
        if self._tree is None:
            return
        # Vue/Quasar prop diff is reference-based, so push a fresh deep
        # copy of the whole tree. Quasar resets its expansion state on a
        # full nodes-prop replacement, so capture the current expanded ids
        # first and re-apply them (plus parent_id) afterwards. The
        # expansion list is keyed by node id, so it survives the
        # dict-identity churn from deep-copy.
        previously_expanded = list(self._tree._props.get("expanded", []) or [])
        self._tree._props["nodes"] = copy.deepcopy(self._root_nodes)
        # Make sure the just-expanded parent is in the set so the user
        # sees the newly-loaded children, and drop any stale sentinel ids.
        keep = [eid for eid in previously_expanded if not eid.endswith(_LOAD_MORE_ID)]
        if parent_id not in keep:
            keep.append(parent_id)
        self._tree._props["expanded"] = keep
        self._tree.update()

    # ------------------------------------------------------------------
    # event handlers
    # ------------------------------------------------------------------

    def _on_select(self, node_id: Optional[str], context: "SessionContext") -> None:
        if not node_id:
            return

        # Sentinel click — load the next batch.
        if node_id.endswith(_LOAD_MORE_ID):
            parent_id = node_id[: -(len("::") + len(_LOAD_MORE_ID))]
            if self._tree is not None:
                self._tree.deselect()
            self._expand_sentinel(parent_id)
            return

        path = Path(node_id)
        if not path.is_file():
            # Folder click toggles expansion, like the eager browser does.
            if self._tree is not None:
                expanded = self._tree._props.get("expanded", [])
                if node_id in expanded:
                    self._tree.collapse([node_id])
                else:
                    self._tree.expand([node_id])
                self._tree.deselect()
            return

        context.active_file = path

        from haybale_studio.editors.code_editor import EDITABLE_EXTS

        ext = path.suffix.lower()
        if ext in self._GRAPH_EXTS:
            self._open_graph_file(path, context)
        elif ext in EDITABLE_EXTS:
            self._open_in_code_editor(path, context)
        else:
            self._open_in_file_viewer(path, context)

    # ------------------------------------------------------------------
    # routing — same payload contract as FileBrowserEditor
    # ------------------------------------------------------------------

    def _open_graph_file(self, path: Path, context: "SessionContext") -> None:
        from haybale_studio.editors.graph_editor import GraphEditor

        app: "HaywireApp" = context.app
        session = context.session
        if app is None or session is None or not hasattr(app, "haystack"):
            return

        entry = app.haystack.open_graph(path)
        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.EDITOR_FOCUSED,
                reveal_editor=GraphEditor.class_identity.registry_key,
                reveal_payload=entry.entry_id,
                reveal_label=entry.display_name,
            )
        )

    def _open_in_code_editor(self, path: Path, context: "SessionContext") -> None:
        session = context.session
        if session is None:
            return
        from haybale_studio.editors.code_editor import CodeEditor

        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.FILE_SELECTED,
                detail=path,
                reveal_editor=CodeEditor.class_identity.registry_key,
                reveal_payload=str(path),
                reveal_label=path.name,
            )
        )

    def _open_in_file_viewer(self, path: Path, context: "SessionContext") -> None:
        session = context.session
        if session is None:
            return
        from haybale_studio.editors.file_viewer import FileViewerEditor

        session.notify_context_changed(
            ContextChangedEvent(
                change_type=ContextChangeType.FILE_SELECTED,
                detail=path,
                reveal_editor=FileViewerEditor.class_identity.registry_key,
                reveal_payload=str(path),
                reveal_label=path.name,
            )
        )

    def _refresh(self, context: "SessionContext") -> None:
        """Drop all caches and rebuild from the workspace root down."""
        self._render_tree(context)
