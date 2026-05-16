# barn/haybale-haystack/haybale_haystack/panels/open_in_haystack.py
"""OpenInHaystackPanel — file-context-menu entry for ``.haywire`` files.

Polls true when the right-clicked file has the ``.haywire`` extension.
On click, resolves a Haystack entry for the path via
``ctx.app_data[HaystackState].open_graph(path)`` then issues
``actions.reveal(GraphEditor, entry.binding_id, entry.display_name)``.

Kept in its own module (separate from the sibling file-action panels
OpenInCodeEditorPanel and OpenInFileViewerPanel that live in haybale-studio)
to make cross-library separation clean.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_haystack.state.haystack_state import HaystackState
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
    actions=FileBrowserActions,
    focus=FileFocus,
    label="Open in Haystack",
    icon=hui.icon.graph,
    order=10,
)
class OpenInHaystackPanel(BasePanel):
    """Open a .haywire graph file in the GraphEditor via the Haystack."""

    actions: FileBrowserActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        f = ctx.data[FileBrowserState].right_clicked_file
        return f is not None and f.suffix.lower() in _GRAPH_EXTS

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        from haybale_graph_editor.editors.graph_editor import GraphEditor

        path = ctx.data[FileBrowserState].right_clicked_file
        if path is None:
            return

        def _do_open() -> None:
            hs = ctx.app_data.get(HaystackState)
            if hs is None:
                return
            entry = hs.open_graph(path)
            self.actions.reveal(GraphEditor, binding_id=entry.binding_id, label=entry.display_name)

        layout.button(
            "Open in Haystack",
            icon=hui.icon.graph,
            on_click=_do_open,
        )
