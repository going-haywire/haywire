"""SessionFileMenuProvider — panel-driven file context menu provider.

Inherits popup/panel infrastructure from BaseContextMenuProvider.
Adds: on_file_context intent, FileBrowserActions implementation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Tuple, TYPE_CHECKING

from haybale_studio.editors._context_menu_base import BaseContextMenuProvider

if TYPE_CHECKING:
    from haywire.ui.editor.base import BaseEditor

logger = logging.getLogger(__name__)


class SessionFileMenuProvider(BaseContextMenuProvider):
    """Panel-driven file-context-menu provider, satisfies FileBrowserActions."""

    # ------------------------------------------------------------------
    # Intent
    # ------------------------------------------------------------------

    def on_file_context(self, pos: Tuple[float, float], path: Path) -> None:
        """User right-clicked a file at screen position ``pos``."""
        from haybale_studio.state.file_browser_state import FileBrowserState
        from haybale_studio.file_focus import FileFocus
        from haybale_studio.editors.file_browser_menu.actions import FileBrowserActions

        # Set transient menu state
        self._context.data[FileBrowserState].right_clicked_file = path

        def _on_close() -> None:
            # Q8A: clear right_clicked_file on dismissal
            try:
                self._context.data[FileBrowserState].right_clicked_file = None
            except KeyError:
                pass

        self._open_menu(FileBrowserActions, FileFocus, pos, on_close=_on_close)

    # ------------------------------------------------------------------
    # FileBrowserActions Protocol implementation
    # ------------------------------------------------------------------

    def reveal(
        self,
        editor_cls: "type[BaseEditor]",
        binding_id: Any,
        label: str,
    ) -> None:
        """Issue a Reveal lifecycle command and close the popup."""
        from haywire.core.session.signals import Reveal

        self._session.publish(Reveal(editor=editor_cls, binding_id=binding_id, label=label))
        if self._open_popup is not None:
            self._open_popup.close()
