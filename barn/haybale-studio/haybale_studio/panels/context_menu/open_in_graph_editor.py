"""OpenInGraphEditorPanel — file-context-menu entry for ``.haywire`` files.

Polls true when the right-clicked file has the ``.haywire`` extension.
On click, resolves a Haystack entry for the path then issues
``actions.reveal(GraphEditor, entry.entry_id, entry.display_name)``.

This panel lives in haybale-studio for PR1 because GraphEditor and
Haystack still live here. PR2 moves this file (and GraphEditor /
HaystackEditor) into a new ``haybale-haystack`` library, where the
panel will be migrated from ``app.haystack.open_graph(...)`` to
``ctx.app_data[HaystackState].open_graph(...)``.

Kept in its own module to make that move a clean rename rather than
disentangling it from sibling panels (OpenInCodeEditorPanel, etc.)
that stay in haybale-studio.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_studio.editors.file_browser_menu.actions import FileBrowserActions
from haybale_studio.file_focus import FileFocus
from haybale_studio.state.file_browser_state import FileBrowserState
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.layout import PanelLayout

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


_GRAPH_EXTS = frozenset({".haywire"})


@panel(
    action=FileBrowserActions,
    focus=FileFocus,
    label="Open in Graph Editor",
    icon=hui.icon.graph,
    order=10,
)
class OpenInGraphEditorPanel(BasePanel):
    """Open a .haywire graph file in the GraphEditor via the Haystack."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        f = ctx.data[FileBrowserState].right_clicked_file.value
        return f is not None and f.suffix.lower() in _GRAPH_EXTS

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
        actions: FileBrowserActions,
    ) -> None:
        from haybale_studio.editors.graph_editor import GraphEditor

        path = ctx.data[FileBrowserState].right_clicked_file.value
        if path is None:
            return

        def _do_open() -> None:
            app = ctx.app
            session = ctx.session
            if app is None or session is None or not hasattr(app, "haystack"):
                return
            entry = app.haystack.open_graph(path)  # type: ignore[union-attr]
            actions.reveal(GraphEditor, payload=entry.entry_id, label=entry.display_name)

        layout.button(
            "Open in Graph Editor",
            icon=hui.icon.graph,
            on_click=_do_open,
        )
