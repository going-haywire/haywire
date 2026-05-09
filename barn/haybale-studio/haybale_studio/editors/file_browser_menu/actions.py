"""FileBrowserActions — Protocol implemented by SessionFileMenuProvider.

Per Q11B: a single method, ``reveal``. Each panel resolves its own
payload (e.g. the "Open in Haystack" panel calls
HaystackState.open_graph(path) to derive an entry_id, then calls
actions.reveal(GraphEditor, entry_id, display_name)).

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
        payload: Any,
        label: str,
    ) -> None:
        """Issue a Reveal lifecycle command and close the menu popup."""
        ...
