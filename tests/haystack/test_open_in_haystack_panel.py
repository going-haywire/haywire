"""OpenInHaystackPanel — file-context-menu entry for .haywire files."""

from pathlib import Path
from unittest.mock import MagicMock

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from tests.conftest import attach_stub_session


def test_panel_polls_true_for_haywire_file():
    from haybale_haystack.panels.file_browser.open_in_haystack import OpenInHaystackPanel
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state = attach_stub_session(FileBrowserState())
    state.right_clicked_file = Path("/tmp/foo.haywire")
    ctx.data = {FileBrowserState: state}

    assert OpenInHaystackPanel.poll(ctx) is True


def test_panel_polls_false_for_non_haywire_file():
    from haybale_haystack.panels.file_browser.open_in_haystack import OpenInHaystackPanel
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state = attach_stub_session(FileBrowserState())
    state.right_clicked_file = Path("/tmp/foo.txt")
    ctx.data = {FileBrowserState: state}

    assert OpenInHaystackPanel.poll(ctx) is False


def test_panel_polls_false_when_no_right_click():
    from haybale_haystack.panels.file_browser.open_in_haystack import OpenInHaystackPanel
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state = attach_stub_session(FileBrowserState())
    # right_clicked_file stays None
    ctx.data = {FileBrowserState: state}

    assert OpenInHaystackPanel.poll(ctx) is False


def test_panel_decorator_metadata():
    from haybale_haystack.panels.file_browser.open_in_haystack import OpenInHaystackPanel
    from haybale_studio.editors.file_browser_menu.actions import FileBrowserActions
    from haybale_studio.file_focus import FileFocus

    # The @panel decorator stores metadata on class_identity
    ident = OpenInHaystackPanel.class_identity
    assert ident.action is FileBrowserActions
    assert ident.focus is FileFocus
    assert "Haystack" in ident.label
