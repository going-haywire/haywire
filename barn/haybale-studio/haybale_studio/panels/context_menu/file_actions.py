"""Context menu panels for file actions in haybale-studio.

Two panels register against ``focus=FileFocus`` and surface in the
FileBrowser's right-click menu for editor types haybale-studio owns:

  - OpenInCodeEditorPanel   — text-editable extensions; reveals CodeEditor.
  - OpenInFileViewerPanel   — any other file (catch-all); reveals FileViewerEditor.

Each panel polls on the right-clicked file's extension, sets active_file
and fires ActiveFileMoved on click (so editors that follow active_file
keep working), then calls ``actions.reveal(editor_cls, payload, label)``.

The third file-context-menu panel (OpenInHaystackPanel for .haywire)
lives in ``haybale-haystack`` (``haybale_haystack/panels/open_in_haystack.py``)
because it depends on HaystackState, which is owned by that library.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from haybale_studio.editors.file_browser_menu.actions import FileBrowserActions
from haybale_studio.file_focus import FileFocus
from haybale_studio.state.file_browser_state import FileBrowserState
from haywire.core.session.context_signals import ActiveFileMoved
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.layout import PanelLayout

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    action=FileBrowserActions,
    focus=FileFocus,
    label="Open in Code Editor",
    icon=hui.icon.edit,
    order=20,
)
class OpenInCodeEditorPanel(BasePanel):
    """Open an editable text file in the CodeEditor."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        from haybale_studio.editors.code_editor import EDITABLE_EXTS

        f = ctx.data[FileBrowserState].right_clicked_file.value
        return f is not None and f.suffix.lower() in EDITABLE_EXTS

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: FileBrowserActions,
    ) -> None:
        from haybale_studio.editors.code_editor import CodeEditor

        path = ctx.data[FileBrowserState].right_clicked_file.value
        if path is None:
            return

        def _do_open() -> None:
            session = ctx.session
            if session is None:
                return
            ctx.active_file.value = path
            session.signal(ActiveFileMoved())
            actions.reveal(CodeEditor, payload=str(path), label=path.name)

        layout.button(
            "Open in Code Editor",
            icon=hui.icon.edit,
            on_click=_do_open,
        )


@panel(
    action=FileBrowserActions,
    focus=FileFocus,
    label="Open in File Viewer",
    icon=hui.icon.library_component,
    order=30,
)
class OpenInFileViewerPanel(BasePanel):
    """Open any file in the read-only FileViewerEditor (catch-all fallback)."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        f = ctx.data[FileBrowserState].right_clicked_file.value
        return isinstance(f, Path) and f.is_file()

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: FileBrowserActions,
    ) -> None:
        from haybale_studio.editors.file_viewer import FileViewerEditor

        path = ctx.data[FileBrowserState].right_clicked_file.value
        if path is None:
            return

        def _do_open() -> None:
            session = ctx.session
            if session is None:
                return
            ctx.active_file.value = path
            session.signal(ActiveFileMoved())
            actions.reveal(FileViewerEditor, payload=str(path), label=path.name)

        layout.button(
            "Open in File Viewer",
            icon=hui.icon.library_component,
            on_click=_do_open,
        )
