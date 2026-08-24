"""Context menu panels for file actions in haybale-studio.

Two panels register against ``surface=FileMenu`` and appear in the
FileBrowser's right-click menu for editor types haybale-studio owns:

  - OpenInCodeEditorMenuPanel   — text-editable extensions; reveals CodeEditor.
  - OpenInFileViewerMenuPanel   — any other file (catch-all); reveals FileViewerEditor.

Each panel polls on the right-clicked file's extension, sets
``active_file`` on click (which synthetically emits
``SessionContext.active_file`` on the bus so editors that follow
active_file keep working), then calls
``actions.reveal(editor_cls, binding_id, label)``.

The third file-context-menu panel (OpenInHaystackMenuPanel for .haywire)
lives in ``haybale-haystack`` (``haybale_haystack/panels/file_browser/menu/file.py``)
because it depends on HaystackState, which is owned by that library.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from haybale_studio.surfaces import FileActions, FileMenu
from haybale_studio.state.file_browser_state import FileBrowserState
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.layout import PanelLayout

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=FileMenu,
    label="Open in Code Editor",
    icon=hui.icon.edit,
    order=20,
)
class OpenInCodeEditorMenuPanel(BasePanel):
    """Open an editable text file in the CodeEditor."""

    actions: FileActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        from haybale_studio.editors.code_editor import EDITABLE_EXTS

        f = ctx.data[FileBrowserState].right_clicked_file
        return f is not None and f.suffix.lower() in EDITABLE_EXTS

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        from haybale_studio.editors.code_editor import CodeEditor

        path = ctx.data[FileBrowserState].right_clicked_file
        if path is None:
            return

        def _do_open() -> None:
            session = ctx.session
            if session is None:
                return
            # Assigning emits SessionContext.active_file synthetically.
            ctx.active_file = path
            self.actions.reveal(CodeEditor, binding_id=str(path), label=path.name)

        with layout:
            hui.menu_row(
                "Open in Code Editor",
                icon=hui.icon.edit,
                on_click=_do_open,
            )


@panel(
    surface=FileMenu,
    label="Open in File Viewer",
    icon=hui.icon.library_component,
    order=30,
)
class OpenInFileViewerMenuPanel(BasePanel):
    """Open any file in the read-only FileViewerEditor (catch-all fallback)."""

    actions: FileActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        f = ctx.data[FileBrowserState].right_clicked_file
        return isinstance(f, Path) and f.is_file()

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        from haybale_studio.editors.file_viewer import FileViewerEditor

        path = ctx.data[FileBrowserState].right_clicked_file
        if path is None:
            return

        def _do_open() -> None:
            session = ctx.session
            if session is None:
                return
            # Assigning emits SessionContext.active_file synthetically.
            ctx.active_file = path
            self.actions.reveal(FileViewerEditor, binding_id=str(path), label=path.name)

        with layout:
            hui.menu_row(
                "Open in File Viewer",
                icon=hui.icon.library_component,
                on_click=_do_open,
            )
