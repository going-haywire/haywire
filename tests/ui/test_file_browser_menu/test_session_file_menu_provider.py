"""SessionFileMenuProvider — tests for the file context menu provider.

Mirrors the test pattern in tests/ui/test_canvas_handlers/test_session_context_menu_provider.py.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import haywire.core.graph.editor  # noqa: F401 — circular-import guard


def _make_provider_under_test(panels=None):
    """Build a provider with mocked dependencies."""
    from haybale_studio.editors.file_browser_menu.provider import SessionFileMenuProvider
    from haybale_studio.state.file_browser_state import FileBrowserState

    ctx = MagicMock()
    state_inst = FileBrowserState()
    ctx.data = {FileBrowserState: state_inst}
    session = MagicMock()
    panel_registry = MagicMock()
    panel_registry.get_panels_for.return_value = panels or []

    provider = SessionFileMenuProvider(context=ctx, session=session, panel_registry=panel_registry)
    return provider, ctx, session, panel_registry, state_inst


def test_on_file_context_sets_right_clicked_file():
    provider, ctx, session, panel_registry, state = _make_provider_under_test()
    p = Path("/tmp/foo.haywire")
    with patch.object(provider, "_build_popup") as mock_popup_factory:
        mock_popup_factory.return_value = MagicMock()
        provider.on_file_context(pos=(10, 20), path=p)

    assert state.right_clicked_file.value == p


def test_on_close_clears_right_clicked_file():
    provider, ctx, session, panel_registry, state = _make_provider_under_test()
    p = Path("/tmp/foo.haywire")

    captured_on_close = {}

    def _capture(cb):
        captured_on_close["cb"] = cb

    popup = MagicMock()
    popup.on_close = _capture

    with patch.object(provider, "_build_popup", return_value=popup):
        provider.on_file_context(pos=(0, 0), path=p)

    assert state.right_clicked_file.value == p
    captured_on_close["cb"]()  # Simulate menu close
    assert state.right_clicked_file.value is None


def test_reveal_issues_lifecycle_and_closes_popup():
    provider, ctx, session, panel_registry, state = _make_provider_under_test()
    popup = MagicMock()
    provider._open_popup = popup

    editor_cls = MagicMock()
    provider.reveal(editor_cls, payload="payload-x", label="My Editor")

    # session.lifecycle was called with a Reveal command
    session.lifecycle.assert_called_once()
    call = session.lifecycle.call_args[0][0]
    assert call.editor is editor_cls
    assert call.payload == "payload-x"
    assert call.label == "My Editor"
    # And the popup got closed
    popup.close.assert_called_once()


def test_panels_filtered_by_poll():
    """Only panels whose poll() returns True are drawn."""
    visible_panel_cls = MagicMock()
    visible_panel_cls.poll.return_value = True
    hidden_panel_cls = MagicMock()
    hidden_panel_cls.poll.return_value = False

    provider, ctx, session, panel_registry, state = _make_provider_under_test(
        panels=[visible_panel_cls, hidden_panel_cls]
    )

    popup = MagicMock()
    with patch.object(provider, "_build_popup", return_value=popup):
        provider.on_file_context(pos=(0, 0), path=Path("/tmp/foo"))

    visible_panel_cls.assert_called_once()  # instantiated
    hidden_panel_cls.assert_not_called()  # never instantiated


def test_no_panels_no_popup_open():
    """If no panel polls True, the popup is not opened."""
    panel_cls = MagicMock()
    panel_cls.poll.return_value = False
    provider, ctx, session, panel_registry, state = _make_provider_under_test(panels=[panel_cls])
    popup = MagicMock()

    with patch.object(provider, "_build_popup", return_value=popup):
        provider.on_file_context(pos=(0, 0), path=Path("/tmp/foo"))

    popup.open.assert_not_called()
