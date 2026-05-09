"""End-to-end smoke: a panel with focus=FileFocus appears in the menu
when right_clicked_file is set, and reveal() fires."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import haywire.core.graph.editor  # noqa: F401 — circular-import guard

from haywire.core.library.identity import LibraryIdentity

_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    description="test",
    url="",
    help_url="",
    author="",
    author_url="",
    folder_path="/tmp/fake",
    module_name="fake",
    id="fake",
)


def test_panel_appears_and_reveal_fires():
    from haywire.ui.panel.base import BasePanel
    from haywire.ui.panel.decorator import panel
    from haywire.ui.panel.registry import PanelRegistry
    from haybale_studio.file_focus import FileFocus
    from haybale_studio.state.file_browser_state import FileBrowserState
    from haybale_studio.editors.file_browser_menu.actions import FileBrowserActions
    from haybale_studio.editors.file_browser_menu.provider import SessionFileMenuProvider

    @panel(
        action=FileBrowserActions,
        focus=FileFocus,
        label="Smoke Open",
        registry_id="smoke_open_panel",
    )
    class SmokeOpenPanel(BasePanel):
        @classmethod
        def poll(cls, ctx) -> bool:
            f = ctx.data[FileBrowserState].right_clicked_file.value
            return f is not None and f.suffix == ".smoke"

        def draw(self, ctx, layout, actions):
            f = ctx.data[FileBrowserState].right_clicked_file.value
            # Simulate user clicking the menu item
            actions.reveal(MagicMock(), payload=str(f), label=f.name)

    # Build a fresh registry and register only our smoke panel
    registry = PanelRegistry()
    registry._register_class(SmokeOpenPanel, _FAKE_LIBRARY_IDENTITY)

    ctx = MagicMock()
    state = FileBrowserState()
    ctx.data = {FileBrowserState: state}
    session = MagicMock()
    provider = SessionFileMenuProvider(context=ctx, session=session, panel_registry=registry)

    popup = MagicMock()
    with patch.object(provider, "_build_popup", return_value=popup):
        provider.on_file_context(pos=(0, 0), path=Path("/tmp/foo.smoke"))

    # reveal() was called inside draw(), which called session.lifecycle
    session.lifecycle.assert_called_once()
    # And the popup was opened (at least one visible panel existed)
    popup.open.assert_called_once()


def test_panel_skipped_when_extension_doesnt_match():
    from haywire.ui.panel.base import BasePanel
    from haywire.ui.panel.decorator import panel
    from haywire.ui.panel.registry import PanelRegistry
    from haybale_studio.file_focus import FileFocus
    from haybale_studio.state.file_browser_state import FileBrowserState
    from haybale_studio.editors.file_browser_menu.actions import FileBrowserActions
    from haybale_studio.editors.file_browser_menu.provider import SessionFileMenuProvider

    @panel(
        action=FileBrowserActions,
        focus=FileFocus,
        label="Smoke OnlySmokeExt",
        registry_id="smoke_only_ext_panel",
    )
    class SmokeOnlyPanel(BasePanel):
        @classmethod
        def poll(cls, ctx) -> bool:
            f = ctx.data[FileBrowserState].right_clicked_file.value
            return f is not None and f.suffix == ".smoke"

        def draw(self, ctx, layout, actions):
            actions.reveal(MagicMock(), payload="", label="x")

    registry = PanelRegistry()
    registry._register_class(SmokeOnlyPanel, _FAKE_LIBRARY_IDENTITY)

    ctx = MagicMock()
    state = FileBrowserState()
    ctx.data = {FileBrowserState: state}
    session = MagicMock()
    provider = SessionFileMenuProvider(context=ctx, session=session, panel_registry=registry)

    popup = MagicMock()
    with patch.object(provider, "_build_popup", return_value=popup):
        # Right-click a file with a DIFFERENT extension — poll() must return False
        provider.on_file_context(pos=(0, 0), path=Path("/tmp/foo.txt"))

    popup.open.assert_not_called()
    session.lifecycle.assert_not_called()
