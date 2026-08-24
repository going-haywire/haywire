"""The file-browser right-click menu.

When the user right-clicks a file in FileBrowser, ``SessionFileMenuProvider``
sets ``FileBrowserState.right_clicked_file``, ``FileMenu.poll(ctx)`` returns
True, and the panels registered against this surface are filtered by their
own ``poll(ctx)`` and rendered into the menu popup.
"""

from __future__ import annotations

from typing import Any, ClassVar, Protocol, TYPE_CHECKING, runtime_checkable

from haywire.ui.surface import Surface

if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor


@runtime_checkable
class FileActions(Protocol):
    """What a file-menu panel may ask its host to do.

    Each panel resolves its own ``binding_id`` — e.g. haystack's "Open in
    Haystack" panel calls ``HaystackState.open_graph(path)`` to derive one,
    then calls ``reveal(GraphEditor, binding_id, display_name)``. The
    GraphEditor lives in haybale-graph-editor and resolves the binding_id
    through GraphAppState at draw time.
    """

    def reveal(
        self,
        editor_cls: "type[BaseEditor]",
        binding_id: Any,
        label: str,
    ) -> None:
        """Issue a Reveal lifecycle command and close the menu popup."""
        ...


class FileMenu(Surface):
    """The file-browser right-click menu."""

    id: ClassVar[str] = "file"
    order: ClassVar[int] = 200  # library-ish, below built-ins (0–99)
    provides = FileActions

    @classmethod
    def poll(cls, ctx: Any) -> bool:
        # Lazy import to avoid module-load ordering with state classes
        from haybale_studio.state.file_browser_state import FileBrowserState

        try:
            return ctx.data[FileBrowserState].right_clicked_file is not None
        except KeyError:
            return False
