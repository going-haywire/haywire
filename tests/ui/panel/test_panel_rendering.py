# tests/ui/panel/test_panel_rendering.py
"""Host-side panel rendering: visible_panels poll-filter + render_panel."""

from unittest.mock import MagicMock, patch

from haywire.core.errors.haywire_exception import HaywireException
from haywire.ui.panel import host_rendering
from haywire.ui.panel.host_rendering import render_panel, visible_panels


def _layout():
    """A PanelLayout-like stub whose .container is a no-op context manager."""
    container = MagicMock()
    container.__enter__ = MagicMock(return_value=container)
    container.__exit__ = MagicMock(return_value=False)
    layout = MagicMock()
    layout.container = container
    return layout


def _panel(name, *, poll=True, on_draw=None):
    """Build a minimal BasePanel-shaped class (poll classmethod + draw)."""
    draw_calls: list = []

    class _Panel:
        actions = None

        @classmethod
        def poll(cls, ctx):
            if isinstance(poll, Exception):
                raise poll
            return poll

        def draw(self, ctx, layout):
            draw_calls.append(self)
            if on_draw is not None:
                on_draw(self)

    _Panel.__name__ = name
    _Panel.draw_calls = draw_calls  # type: ignore[attr-defined]
    return _Panel


# ---------------------------------------------------------------------------
# visible_panels — poll-filter over the error boundary
# ---------------------------------------------------------------------------


def test_visible_panels_keeps_only_visible_in_order():
    a = _panel("A", poll=True)
    hidden = _panel("Hidden", poll=False)
    b = _panel("B", poll=True)
    ctx = MagicMock()

    assert visible_panels([a, hidden, b], ctx) == [a, b]


def test_visible_panels_drops_panel_whose_poll_raises():
    boom = _panel("Boom", poll=ValueError("boom"))
    ok = _panel("Ok", poll=True)
    ctx = MagicMock()

    assert visible_panels([boom, ok], ctx) == [ok]


def test_visible_panels_drops_panel_whose_poll_raises_haywire_exception():
    boom = _panel("Boom", poll=HaywireException("inner failure"))
    ok = _panel("Ok", poll=True)
    ctx = MagicMock()

    assert visible_panels([boom, ok], ctx) == [ok]


def test_visible_panels_empty_when_nothing_visible():
    hidden = _panel("Hidden", poll=False)
    assert visible_panels([hidden], MagicMock()) == []


# ---------------------------------------------------------------------------
# render_panel — instantiate, inject host, draw under the boundary
# ---------------------------------------------------------------------------


def test_render_panel_draws_and_returns_true():
    p = _panel("P")
    ctx = MagicMock()

    assert render_panel(p, ctx, _layout()) is True
    assert len(p.draw_calls) == 1


def test_render_panel_catches_draw_error_and_renders_error_label():
    def _raise(_self):
        raise RuntimeError("draw failed")

    bad = _panel("Bad", on_draw=_raise)
    ctx = MagicMock()
    layout = _layout()

    with patch.object(host_rendering.hui, "error_label") as error_label:
        rendered = render_panel(bad, ctx, layout)

    # Draw raised, so it returns False, but the host stays alive and shows the error.
    assert rendered is False
    error_label.assert_called_once()


def test_render_panel_injects_actions_host_when_provided():
    seen = {}

    def _capture(panel):
        seen["actions"] = panel.actions

    p = _panel("P", on_draw=_capture)
    host = object()
    ctx = MagicMock()

    render_panel(p, ctx, _layout(), actions_host=host)

    assert seen["actions"] is host


def test_render_panel_leaves_actions_none_when_no_host():
    seen = {}

    def _capture(panel):
        seen["actions"] = panel.actions

    p = _panel("P", on_draw=_capture)
    ctx = MagicMock()

    render_panel(p, ctx, _layout())

    assert seen["actions"] is None
