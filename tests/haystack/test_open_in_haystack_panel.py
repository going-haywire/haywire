"""OpenInHaystackPanel — file-context-menu entry for .haywire files."""

from pathlib import Path
from unittest.mock import MagicMock


from tests.conftest import attach_stub_session


def test_panel_polls_true_for_haywire_file():
    from haybale_haystack.panels.file_browser.menu.file import OpenInHaystackMenuPanel as OpenInHaystackPanel
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state = attach_stub_session(FileBrowserState())
    state.right_clicked_file = Path("/tmp/foo.haywire")
    ctx.data = {FileBrowserState: state}

    assert OpenInHaystackPanel.poll(ctx) is True


def test_panel_polls_false_for_non_haywire_file():
    from haybale_haystack.panels.file_browser.menu.file import OpenInHaystackMenuPanel as OpenInHaystackPanel
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state = attach_stub_session(FileBrowserState())
    state.right_clicked_file = Path("/tmp/foo.txt")
    ctx.data = {FileBrowserState: state}

    assert OpenInHaystackPanel.poll(ctx) is False


def test_panel_polls_false_when_no_right_click():
    from haybale_haystack.panels.file_browser.menu.file import OpenInHaystackMenuPanel as OpenInHaystackPanel
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state = attach_stub_session(FileBrowserState())
    # right_clicked_file stays None
    ctx.data = {FileBrowserState: state}

    assert OpenInHaystackPanel.poll(ctx) is False


def test_panel_decorator_metadata():
    from haybale_haystack.panels.file_browser.menu.file import OpenInHaystackMenuPanel as OpenInHaystackPanel
    from haybale_studio.surfaces import FileActions, FileMenu

    # The @panel decorator stores metadata on class_identity
    ident = OpenInHaystackPanel.class_identity
    assert ident.surface is FileMenu
    assert ident.hosts == ()
    assert "Haystack" in ident.label
    # The verbs the panel calls come from its surface's contract, which the
    # host is checked against — a library adding a panel to another library's
    # surface needs no change there.
    assert FileMenu.provides is FileActions
