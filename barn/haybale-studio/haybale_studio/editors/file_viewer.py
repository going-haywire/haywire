# packages/haywire-app/src/haywire_studio/editors/file_viewer.py
"""
FileViewerEditor — displays the contents of the file selected in FileBrowserEditor.

Occupies a middle-area tab ('file_viewer'). Reacts to FILE_SELECTED events
and renders the file contents with basic syntax highlighting via ui.code,
or as rendered markdown for .md files. Binary files and oversized files
show an appropriate message instead.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent
    from nicegui.element import Element


_MAX_DISPLAY_BYTES = 512 * 1024  # 512 KB

_LANGUAGE_MAP: dict = {
    ".py": "python",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".js": "javascript",
    ".ts": "typescript",
    ".css": "css",
    ".html": "html",
    ".xml": "xml",
    ".sh": "bash",
    ".txt": "",
}


@editor(
    label="File Viewer",
    icon=hui.icon.library_component,
    default_slot="main",
    opens="on_payload",
    context_field="active_file",
    description="Displays the contents of a file selected in the Files browser.",
)
class FileViewerEditor(BaseEditor):
    """
    Renders file contents in the middle area.

    Responds to FILE_SELECTED events. Supports syntax-highlighted code
    (via ui.code), rendered markdown, and plain text. Binary files and
    files over 512 KB show an informational message.
    """

    def __init__(self):
        self._last_file: Optional[Path] = None

    def _resolve_path(self) -> Optional[Path]:
        """Return the file path this tab is pinned to, via binding.payload."""
        if self.binding is None or self.binding.payload is None:
            return None
        return Path(self.binding.payload)

    def poll(self, context: "SessionContext", event: "ContextChangedEvent") -> bool:
        """Redraw when DATA_MUTATED touches this file, otherwise stay put.

        Each FileViewer instance is pinned to one file via its binding
        payload. FILE_SELECTED events no longer drive redraws — a different
        file means a different tab.
        """
        return False

    def draw(self, context: "SessionContext", container: "Element") -> None:
        self._last_file = self._resolve_path()

        with container:
            with ui.column().classes("w-full h-full gap-0"):
                # Slim header showing the open file path
                with (
                    ui.row()
                    .classes("w-full items-center px-3 gap-2 flex-shrink-0 border-b")
                    .style("min-height: 32px; background: var(--hw-bg-page);")
                ):
                    ui.icon("description", size="14px").classes("hw-text-dim")
                    label_text = str(self._last_file) if self._last_file else "No file open"
                    label_cls = "hw-text-body" if self._last_file else "hw-text-muted"
                    ui.label(label_text).classes(f"text-xs {label_cls} truncate font-mono flex-1")

                # Content area
                with ui.scroll_area().classes("flex-1 w-full"):
                    with ui.column().classes("w-full"):
                        if self._last_file is not None:
                            self._render_content(self._last_file)
                        else:
                            hui.empty_state(
                                "Select a file from the Files panel",
                                icon=hui.icon.folder_open,
                            )

    def _render_content(self, path: Path) -> None:
        if not path.exists():
            ui.label(f"File not found: {path}").classes("hw-text-danger text-sm p-4")
            return

        try:
            size = path.stat().st_size
        except OSError as exc:
            ui.label(f"Cannot read file: {exc}").classes("hw-text-danger text-sm p-4")
            return

        if size > _MAX_DISPLAY_BYTES:
            ui.label(f"File too large to display ({size // 1024:,} KB — limit 512 KB).").classes(
                "hw-text-warning text-sm p-4"
            )
            return

        # Try UTF-8; treat decode failure as binary
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            hui.empty_state("Binary file — cannot display as text", icon=hui.icon.empty_binary)
            return
        except OSError as exc:
            ui.label(f"Error reading file: {exc}").classes("hw-text-danger text-sm p-4")
            return

        ext = path.suffix.lower()
        lang = _LANGUAGE_MAP.get(ext)  # None = unknown type, '' = plain text

        # File info bar
        with (
            ui.row()
            .classes("w-full items-center gap-2 px-3 py-1 border-b flex-shrink-0")
            .style("background: var(--hw-bg-surface); min-height: 28px;")
        ):
            ui.label(path.name).classes("text-xs font-medium hw-text-body")
            if lang:
                ui.badge(lang).props("color=blue-grey rounded outline").classes("text-xs")
            ui.label(f"{size:,} B").classes("text-xs hw-text-dim ml-auto")

        # Content
        if ext == ".md":
            ui.markdown(content).classes("w-full p-4 text-sm").style("max-width: none;")
        elif lang is not None:
            # Known type — syntax highlight
            ui.code(content, language=lang or "text").classes("w-full text-xs").style(
                "border-radius: 0; min-height: 100%;"
            )
        else:
            # Unknown / binary-safe text — plain monospace
            ui.code(content, language="text").classes("w-full text-xs").style(
                "border-radius: 0; min-height: 100%;"
            )

    def get_tab_label(self, context: "SessionContext") -> str:
        path = self._resolve_path()
        if path is not None:
            return path.name
        return self.class_identity.label

    def cleanup(self) -> None:
        pass
