# barn/haybale-haystack/haybale_haystack/panels/file_browser/menu/file.py
"""OpenInHaystackMenuPanel — file-context-menu entry for ``.haywire`` files.

Polls true when the right-clicked file has the ``.haywire`` extension.
On click, resolves a Haystack entry for the path via
``ctx.app_data[HaystackState].open_graph(path)``. This only adds the graph
to the haystack list — it does NOT reveal a GraphEditor tab. The user opens
it in an editor by selecting the new entry from the haystack list.

Kept in its own module (separate from the sibling file-action panels
OpenInCodeEditorMenuPanel and OpenInFileViewerMenuPanel that live in haybale-studio)
to make cross-library separation clean.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_haystack.state.haystack_state import HaystackState
from haybale_studio.surfaces import FileActions, FileMenu
from haybale_studio.state.file_browser_state import FileBrowserState
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.layout import PanelLayout

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


_GRAPH_EXTS = frozenset({".haywire"})


@panel(
    surface=FileMenu,
    label="Load into Haystack",
    icon=hui.icon.graph,
    order=10,
)
class OpenInHaystackMenuPanel(BasePanel):
    """Load a .haywire graph file into the Haystack (does not open an editor tab)."""

    actions: FileActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        f = ctx.data[FileBrowserState].right_clicked_file
        return f is not None and f.suffix.lower() in _GRAPH_EXTS

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        path = ctx.data[FileBrowserState].right_clicked_file
        if path is None:
            return

        def _do_load() -> None:
            hs = ctx.app_data.get(HaystackState)
            if hs is None:
                return
            hs.open_graph(path)

        with layout:
            hui.menu_row(
                "Load into Haystack",
                icon=hui.icon.graph,
                on_click=_do_load,
            )
