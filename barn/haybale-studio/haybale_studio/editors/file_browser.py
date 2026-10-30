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

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from nicegui import ui

from haywire.core.access import AccessTier
from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import SlotName
from haywire.ui.elements.folder_tree import FolderTreeModel, folder_tree

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext
    from nicegui.element import Element


@editor(
    label="Files",
    icon=hui.icon.folder,
    default_slot=SlotName.ACTION,
    description=(
        "Project file tree, eager-then-lazy: three levels are loaded up"
        " front, then 'Click to load children' sentinels appear at deeper"
        " folders so the user can pull in three more levels on demand."
    ),
    order=10,
    requires=AccessTier.VIEW,
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

    def __init__(self, wrapper):
        super().__init__(wrapper)
        self._root_path: Optional[Path] = None
        self._tree_container = None
        self._tree: Optional[ui.tree] = None
        self._model: Optional[FolderTreeModel] = None
        # Lazily-constructed per-session file context-menu provider.
        self._menu_provider = None

    # ------------------------------------------------------------------
    # render
    # ------------------------------------------------------------------

    # Tree connector-line styling lives in the framework shell as the reusable
    # `.hw-tree` class (see haywire.ui.app.shell._static_css). The tree opts in
    # by adding `hw-tree` to its classes below — no per-editor CSS injection,
    # so it survives a browser refresh and avoids the Vue-mount race that the
    # old per-draw() ui.add_css() caused.

    def draw(self, context: "SessionContext", container: "Element") -> None:
        app = context.app
        if app and hasattr(app, "workspace_root"):
            self._root_path = Path(app.workspace_root)

        with container:
            with ui.column().classes("w-full h-full gap-0"):
                name = self._root_path.name if self._root_path else "No project"
                with hui.slot_header(name, icon=hui.icon.folder_open):
                    # Burger menu — matches the Marketplace header pattern.
                    with (
                        ui.button(icon="more_vert")
                        .props("flat round dense size=sm")
                        .classes("flex-shrink-0")
                    ):
                        with ui.menu():
                            ui.menu_item(
                                "Refresh",
                                on_click=lambda: self._refresh(context),
                            )

                with ui.scroll_area().classes("flex-1 w-full"):
                    self._tree_container = ui.column().classes("w-full p-1 gap-0")
                    self._render_tree(context)

    def _render_tree(self, context: "SessionContext") -> None:
        if self._tree_container is None:
            return
        self._tree_container.clear()
        self._model = None

        if self._root_path is None or not self._root_path.exists():
            with self._tree_container:
                hui.hint("No project loaded").classes("p-2")
            return

        self._model = FolderTreeModel(self._root_path, exclude_dirs=self._EXCLUDE_DIRS)
        if not self._model.nodes:
            with self._tree_container:
                hui.hint("Project folder is empty").classes("p-2")
            return

        with self._tree_container:
            self._tree = folder_tree(
                self._model,
                on_select=lambda path: self._on_select(path, context),
            )
            # Wire right-click on individual tree nodes.  Quasar's q-tree
            # doesn't expose a per-node contextmenu signal, and emitting from
            # inside a scoped slot with `$emit('node-context', …)` doesn't
            # reliably bubble out of the q-tree component.  Instead we:
            #   1. Tag each node's header `<div>` in the default-header slot
            #      with `data-file-key` (the node id, i.e. the path string).
            #   2. Attach a single `contextmenu` listener to the q-tree's
            #      outer element with a JS arg-extractor that walks
            #      `event.target.closest('[data-file-key]')` to find which
            #      row was clicked, plus reads clientX/clientY.
            self._tree.add_slot(
                "default-header",
                """
                <div :data-file-key="props.key" style="display:contents">
                    {{ props.node.label }}
                </div>
                """,
            )
            self._tree.on(
                "contextmenu",
                lambda e: self._on_node_context(
                    e.args.get("key") if isinstance(e.args, dict) else None,
                    float(e.args.get("x", 0)) if isinstance(e.args, dict) else 0.0,
                    float(e.args.get("y", 0)) if isinstance(e.args, dict) else 0.0,
                    context,
                ),
                js_handler="""(event) => {
                    event.preventDefault();
                    const el = event.target.closest('[data-file-key]');
                    if (!el) return;
                    emit({
                        key: el.getAttribute('data-file-key'),
                        x: event.clientX,
                        y: event.clientY,
                    });
                }""",
            )

    # ------------------------------------------------------------------
    # event handlers
    # ------------------------------------------------------------------

    def _ensure_menu_provider(self, context: "SessionContext"):
        """Lazily construct and cache the file context-menu provider for this session."""
        if self._menu_provider is None:
            from haybale_studio.editors.file_browser_menu.provider import SessionFileMenuProvider

            panel_registry = context.app.panel_registry
            self._menu_provider = SessionFileMenuProvider(
                context=context,
                session=context.session,
                panel_registry=panel_registry,
            )
        return self._menu_provider

    def _on_node_context(
        self,
        node_id: Optional[str],
        screen_x: float,
        screen_y: float,
        context: "SessionContext",
    ) -> None:
        """User right-clicked a tree node — open the file context menu."""
        if not node_id or (self._model is not None and self._model.is_sentinel(node_id)):
            return
        path = Path(node_id)
        if not path.is_file():
            return  # Folders don't get a context menu yet
        provider = self._ensure_menu_provider(context)
        provider.on_file_context(pos=(screen_x, screen_y), path=path)

    def _on_select(self, path: Path, context: "SessionContext") -> None:
        """Left-click handler.

        Files: select the file (assigning ``active_file`` emits the
        synthetic ``SessionContext.active_file`` signal on the session
        bus). No editor opens — that's right-click's job via the file
        context menu. Folder expansion and sentinel loading are handled
        by ``folder_tree``.
        """
        if not path.is_file():
            return
        # Editors that follow ``active_file`` (e.g. NodeSourceEditor's "follow
        # active file" mode) react via the signal_field descriptor.
        context.active_file = path

    def _refresh(self, context: "SessionContext") -> None:
        """Drop all caches and rebuild from the workspace root down."""
        self._render_tree(context)
