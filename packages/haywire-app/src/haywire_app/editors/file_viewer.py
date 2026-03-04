# packages/haywire-app/src/haywire_app/editors/file_viewer.py
"""
FileViewerEditor — displays the contents of the file selected in FileBrowserEditor.

Occupies a middle-area tab ('file_viewer'). Reacts to FILE_SELECTED events
and renders the file contents with basic syntax highlighting via ui.code,
or as rendered markdown for .md files. Binary files and oversized files
show an appropriate message instead.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from nicegui import ui

from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.context_events import ContextChangeType

if TYPE_CHECKING:
    from haywire.ui.context import SessionContext
    from haywire.ui.context_events import ContextChangedEvent


_MAX_DISPLAY_BYTES = 512 * 1024  # 512 KB

_LANGUAGE_MAP: dict = {
    '.py':   'python',
    '.json': 'json',
    '.toml': 'toml',
    '.yaml': 'yaml',
    '.yml':  'yaml',
    '.js':   'javascript',
    '.ts':   'typescript',
    '.css':  'css',
    '.html': 'html',
    '.xml':  'xml',
    '.sh':   'bash',
    '.txt':  '',
}


@editor(
    registry_id='file_viewer',
    label='File Viewer',
    icon='description',
    default_area='middle',
    description='Displays the contents of a file selected in the Files browser.',
)
class FileViewerEditor(BaseEditor):
    """
    Renders file contents in the middle area.

    Responds to FILE_SELECTED events. Supports syntax-highlighted code
    (via ui.code), rendered markdown, and plain text. Binary files and
    files over 512 KB show an informational message.
    """

    def __init__(self):
        self._header_label: Optional[ui.label] = None
        self._content_area = None

    def render(self, container, context: 'SessionContext') -> None:
        with container:
            with ui.column().classes('w-full h-full gap-0'):
                # Slim header showing the open file path
                with ui.row().classes(
                    'w-full items-center px-3 gap-2 flex-shrink-0 border-b'
                ).style('min-height: 32px; background: var(--hw-bg-page);'):
                    ui.icon('description', size='14px').classes('hw-text-dim')
                    self._header_label = ui.label('No file open').classes(
                        'text-xs hw-text-muted truncate font-mono flex-1'
                    )

                # Content area — cleared and rebuilt on every FILE_SELECTED event
                with ui.scroll_area().classes('flex-1 w-full'):
                    self._content_area = ui.column().classes('w-full')
                    with self._content_area:
                        self._show_placeholder()

    def _show_placeholder(self) -> None:
        with ui.column().classes(
            'w-full items-center justify-center gap-3'
        ).style('padding: 80px 0;'):
            ui.icon('folder_open', size='40px').classes('hw-text-dim')
            ui.label('Select a file from the Files panel').classes('text-sm hw-text-muted')

    def on_context_changed(
        self, event: 'ContextChangedEvent', context: 'SessionContext'
    ) -> None:
        if event.change_type != ContextChangeType.FILE_SELECTED:
            return
        path = context.active_file
        if path is None:
            return
        self._display_file(Path(path))

    def _display_file(self, path: Path) -> None:
        # Update header
        if self._header_label is not None:
            self._header_label.text = str(path)
            self._header_label.classes(remove='hw-text-muted', add='hw-text-body')

        if self._content_area is None:
            return

        self._content_area.clear()
        with self._content_area:
            self._render_content(path)

    def _render_content(self, path: Path) -> None:
        if not path.exists():
            ui.label(f'File not found: {path}').classes('text-red-400 text-sm p-4')
            return

        try:
            size = path.stat().st_size
        except OSError as exc:
            ui.label(f'Cannot read file: {exc}').classes('text-red-400 text-sm p-4')
            return

        if size > _MAX_DISPLAY_BYTES:
            ui.label(
                f'File too large to display ({size // 1024:,} KB — limit 512 KB).'
            ).classes('text-yellow-400 text-sm p-4')
            return

        # Try UTF-8; treat decode failure as binary
        try:
            content = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            with ui.column().classes('w-full items-center gap-3').style('padding: 60px 0;'):
                ui.icon('block', size='36px').classes('hw-text-dim')
                ui.label('Binary file — cannot display as text').classes(
                    'text-sm hw-text-muted'
                )
            return
        except OSError as exc:
            ui.label(f'Error reading file: {exc}').classes('text-red-400 text-sm p-4')
            return

        ext = path.suffix.lower()
        lang = _LANGUAGE_MAP.get(ext)  # None = unknown type, '' = plain text

        # File info bar
        with ui.row().classes('w-full items-center gap-2 px-3 py-1 border-b flex-shrink-0').style(
            'background: var(--hw-bg-surface); min-height: 28px;'
        ):
            ui.label(path.name).classes('text-xs font-medium hw-text-body')
            if lang:
                ui.badge(lang).props('color=blue-grey rounded outline').classes('text-xs')
            ui.label(f'{size:,} B').classes('text-xs hw-text-dim ml-auto')

        # Content
        if ext == '.md':
            ui.markdown(content).classes('w-full p-4 text-sm').style(
                'max-width: none;'
            )
        elif lang is not None:
            # Known type — syntax highlight
            ui.code(content, language=lang or 'text').classes('w-full text-xs').style(
                'border-radius: 0; min-height: 100%;'
            )
        else:
            # Unknown / binary-safe text — plain monospace
            ui.code(content, language='text').classes('w-full text-xs').style(
                'border-radius: 0; min-height: 100%;'
            )

    def get_tab_label(self, context: 'SessionContext') -> str:
        path = getattr(context, 'active_file', None)
        if path is not None:
            return Path(path).name
        return self.class_identity.label

    def cleanup(self) -> None:
        pass
