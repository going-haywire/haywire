"""FileFocus — discriminator for panels that appear in the file context menu.

When the user right-clicks a file in FileBrowser, SessionFileMenuProvider
sets FileBrowserState.right_clicked_file; FileFocus.available(ctx) returns
True; PanelRegistry then yields panels declared with focus=FileFocus, which
are filtered through poll(ctx) and rendered in the menu popup.

Mirrors NodeFocus / EdgeFocus / etc. in the same focuses package.
"""

from __future__ import annotations

from typing import Any, ClassVar

from haywire.ui.panel.focus import Focus


class FileFocus(Focus):
    """Active when the user has just right-clicked a file in FileBrowser."""

    id: ClassVar[str] = "file"
    label: ClassVar[str] = "File"
    icon: ClassVar[str] = "description"
    order: ClassVar[int] = 200  # library-ish, below built-ins (0–99)

    @classmethod
    def available(cls, ctx: Any) -> bool:
        # Lazy import to avoid module-load ordering with state classes
        from haybale_studio.state.file_browser_state import FileBrowserState

        try:
            return ctx.data[FileBrowserState].right_clicked_file.value is not None
        except KeyError:
            return False
