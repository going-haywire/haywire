"""FileFocus — Focus subclass discriminating panels for the file context menu."""

from pathlib import Path
from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def test_file_focus_id():
    from haybale_studio.file_focus import FileFocus

    assert FileFocus.id == "file"


def test_file_focus_unavailable_when_no_right_click():
    from haybale_studio.file_focus import FileFocus
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state_inst = FileBrowserState()
    ctx.data = {FileBrowserState: state_inst}
    # right_clicked_file starts None
    assert FileFocus.available(ctx) is False


def test_file_focus_available_when_right_clicked():
    from haybale_studio.file_focus import FileFocus
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state_inst = FileBrowserState()
    state_inst.right_clicked_file.value = Path("/tmp/x.haywire")
    ctx.data = {FileBrowserState: state_inst}
    assert FileFocus.available(ctx) is True


def test_file_focus_registered_in_focus_map():
    """Focus.__init_subclass__ should have registered FileFocus by id."""
    from haywire.ui.panel.focus import focus_by_id
    from haybale_studio.file_focus import FileFocus  # noqa: F401 — triggers registration

    assert focus_by_id("file") is FileFocus
