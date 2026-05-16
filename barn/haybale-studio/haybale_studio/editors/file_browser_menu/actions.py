"""FileBrowserActions — Protocol implemented by SessionFileMenuProvider.

Each panel resolves its own binding_id (e.g. the "Open in Haystack" panel
in haybale-haystack calls HaystackState.open_graph(path) to derive a
binding_id, then calls actions.reveal(GraphEditor, binding_id,
display_name)). The GraphEditor itself lives in haybale-graph-editor and
resolves the binding_id through GraphAppState at draw time.

Protocol matching is structural — SessionFileMenuProvider satisfies
this without inheriting from it.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor


@runtime_checkable
class FileBrowserActions(Protocol):
    """Action contract for panels declared with action=FileBrowserActions."""

    def reveal(
        self,
        editor_cls: "type[BaseEditor]",
        binding_id: Any,
        label: str,
    ) -> None:
        """Issue a Reveal lifecycle command and close the menu popup."""
        ...
