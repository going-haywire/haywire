"""SessionFileMenuProvider — tests for the file context menu provider.

Mirrors the test pattern in tests/ui/test_canvas_handlers/test_session_context_menu_provider.py.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch


def _make_provider_under_test(panels=None):
    """Build a provider with mocked dependencies."""
    from haybale_studio.editors.file_browser_menu.provider import SessionFileMenuProvider
    from haybale_studio.state.file_browser_state import FileBrowserState
    from tests.conftest import attach_stub_session

    ctx = MagicMock()
    state_inst = attach_stub_session(FileBrowserState())
    ctx.data = {FileBrowserState: state_inst}
    session = MagicMock()
    panel_registry = MagicMock()
    panel_registry.get_panels.return_value = panels or []

    provider = SessionFileMenuProvider(context=ctx, session=session, panel_registry=panel_registry)
    return provider, ctx, session, panel_registry, state_inst


def _visible_panel():
    """A MagicMock panel class that polls visible, so the popup actually opens.

    ``class_identity.hosts`` must be an empty tuple: the host counts *leaf*
    panels to decide whether to keep the popup, and a bare MagicMock attribute
    would be truthy — reading as a hosting panel and swallowing the menu.
    """
    return _panel_double(polls=True)


def _panel_double(*, polls: bool):
    """A MagicMock panel class with the real attributes the host reads.

    Three of them, all of which a bare MagicMock gets wrong: ``hosts`` (would
    be truthy, so the panel reads as a host rather than a leaf), ``order``
    (would be unsortable), and ``draw_disabled`` (would look overridden, so
    the disabled path would render a no-op and count it as content).
    """
    from haywire.ui.panel.base import BasePanel

    panel_cls = MagicMock()
    panel_cls.poll.return_value = polls
    panel_cls.class_identity.hosts = ()
    panel_cls.class_identity.order = 100
    panel_cls.draw_disabled = BasePanel.draw_disabled
    return panel_cls


def _patched_popup():
    """A Popup double whose ``content`` works as a context manager.

    The host renders the whole tree into the popup before deciding whether to
    open it, so ``content`` has to be enterable even on the discard path.
    """
    content = MagicMock()
    content.__enter__ = MagicMock(return_value=content)
    content.__exit__ = MagicMock(return_value=False)
    popup = MagicMock()
    popup.content = content
    return popup


def test_on_file_context_sets_right_clicked_file():
    provider, ctx, session, panel_registry, state = _make_provider_under_test(panels=[_visible_panel()])
    p = Path("/tmp/foo.haywire")
    with patch.object(provider, "_build_popup", return_value=_patched_popup()):
        provider.on_file_context(pos=(10, 20), path=p)

    assert state.right_clicked_file == p


def test_on_close_clears_right_clicked_file():
    provider, ctx, session, panel_registry, state = _make_provider_under_test(panels=[_visible_panel()])
    p = Path("/tmp/foo.haywire")

    captured_on_close = {}

    def _capture(cb):
        captured_on_close["cb"] = cb

    popup = _patched_popup()
    popup.on_close = _capture

    with patch.object(provider, "_build_popup", return_value=popup):
        provider.on_file_context(pos=(0, 0), path=p)

    assert state.right_clicked_file == p
    captured_on_close["cb"]()  # Simulate menu close
    assert state.right_clicked_file is None


def test_on_close_runs_immediately_when_no_panels_visible():
    """With no visible panel the gesture ends at once — cleanup runs without a popup."""
    provider, ctx, session, panel_registry, state = _make_provider_under_test()
    p = Path("/tmp/foo.haywire")

    popup = _patched_popup()
    with patch.object(provider, "_build_popup", return_value=popup):
        provider.on_file_context(pos=(0, 0), path=p)

    # No popup opened, but the close cleanup still ran: state was reset.
    popup.open.assert_not_called()
    assert state.right_clicked_file is None


def test_reveal_issues_lifecycle_and_closes_popup():
    provider, ctx, session, panel_registry, state = _make_provider_under_test()
    popup = MagicMock()
    provider._open_popup = popup

    editor_cls = MagicMock()
    provider.reveal(editor_cls, binding_id="payload-x", label="My Editor")

    # session.publish was called with a Reveal command
    session.publish.assert_called_once()
    call = session.publish.call_args[0][0]
    assert call.editor is editor_cls
    assert call.binding_id == "payload-x"
    assert call.label == "My Editor"
    # And the popup got closed
    popup.close.assert_called_once()


def test_panels_filtered_by_poll():
    """Only panels whose poll() returns True are drawn."""
    visible_panel_cls = _visible_panel()
    hidden_panel_cls = _panel_double(polls=False)

    provider, ctx, session, panel_registry, state = _make_provider_under_test(
        panels=[visible_panel_cls, hidden_panel_cls]
    )

    popup = _patched_popup()
    with patch.object(provider, "_build_popup", return_value=popup):
        provider.on_file_context(pos=(0, 0), path=Path("/tmp/foo"))

    visible_panel_cls.assert_called_once()  # instantiated
    # Never instantiated: it polls false and inherits the no-op draw_disabled,
    # so the disabled path skips it entirely.
    hidden_panel_cls.assert_not_called()


def test_no_panels_no_popup_open():
    """If no panel polls True, the popup is not opened."""
    panel_cls = _panel_double(polls=False)
    provider, ctx, session, panel_registry, state = _make_provider_under_test(panels=[panel_cls])
    popup = _patched_popup()

    with patch.object(provider, "_build_popup", return_value=popup):
        provider.on_file_context(pos=(0, 0), path=Path("/tmp/foo"))

    popup.open.assert_not_called()
