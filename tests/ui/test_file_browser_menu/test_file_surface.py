"""FileMenu — the surface the file-browser right-click menu opens."""

from pathlib import Path
from unittest.mock import MagicMock


def test_file_menu_id():
    from haybale_studio.surfaces import FileMenu

    assert FileMenu.id == "file"


def test_file_menu_does_not_apply_when_no_right_click():
    from haybale_studio.surfaces import FileMenu
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state_inst = FileBrowserState()
    ctx.data = {FileBrowserState: state_inst}
    # right_clicked_file starts None
    assert FileMenu.poll(ctx) is False


def test_file_menu_applies_when_right_clicked():
    from haybale_studio.surfaces import FileMenu
    from haybale_studio.state.file_browser_state import FileBrowserState

    from tests.conftest import attach_stub_session

    ctx = MagicMock()
    state_inst = attach_stub_session(FileBrowserState())
    state_inst.right_clicked_file = Path("/tmp/x.haywire")
    ctx.data = {FileBrowserState: state_inst}
    assert FileMenu.poll(ctx) is True


def test_file_menu_registered_in_surface_map():
    """Surface.__init_subclass__ should have registered FileMenu by id."""
    from haywire.ui.surface import surface_by_id
    from haybale_studio.surfaces import FileMenu  # noqa: F401 — triggers registration

    assert surface_by_id("file") is FileMenu


def test_file_menu_declares_the_reveal_contract():
    from haybale_studio.surfaces import FileActions, FileMenu

    assert FileMenu.provides is FileActions

    class _Provider:
        def reveal(self, editor_cls, binding_id, label) -> None: ...

    class _NotAProvider:
        pass

    assert isinstance(_Provider(), FileActions)
    assert not isinstance(_NotAProvider(), FileActions)
