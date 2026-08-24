# tests/ui/panel/test_panel_rendering.py
"""Host-side panel rendering: visible_panels poll-filter + render_panel."""

from unittest.mock import MagicMock, patch

from haywire.core.access import AccessTier
from haywire.core.errors.haywire_exception import HaywireException
from haywire.ui.panel import host_rendering
from haywire.ui.panel.base import BasePanel
from haywire.ui.panel.host_rendering import partition_panels, render_panel, visible_panels
from haywire.ui.panel.identity import PanelIdentity


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


def _real_panel(name, *, poll=True, order=100, with_draw_disabled=False):
    """A real BasePanel subclass (needed for partition_panels' access= check
    and for _implements_draw_disabled's identity comparison against
    BasePanel.draw_disabled, which only works against real subclasses)."""
    draw_calls: list = []
    draw_disabled_calls: list = []

    class _Panel(BasePanel):
        actions = None

        @classmethod
        def poll(cls, ctx):
            return poll

        def draw(self, ctx, layout):
            draw_calls.append(self)

        if with_draw_disabled:

            def draw_disabled(self, ctx, layout):
                draw_disabled_calls.append(self)

    _Panel.__name__ = name
    _Panel.class_identity = PanelIdentity(
        registry_id=name, registry_key=f"k:{name}", label=name, order=order
    )
    _Panel.draw_calls = draw_calls  # type: ignore[attr-defined]
    _Panel.draw_disabled_calls = draw_disabled_calls  # type: ignore[attr-defined]
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


# ---------------------------------------------------------------------------
# render_panel(disabled=True) — the draw_disabled() path
# ---------------------------------------------------------------------------


def _ctx_view():
    ctx = MagicMock()
    ctx.can_access.return_value = True
    return ctx


def test_render_panel_disabled_true_default_draw_disabled_is_a_no_op_and_returns_false():
    """A panel implementing only draw() and inheriting the default no-op
    draw_disabled() must still vanish when poll() is false — the
    zero-migration guarantee: every panel that does not opt into greying
    keeps vanishing exactly as it does today."""
    p = _real_panel("OnlyDraw", with_draw_disabled=False)
    rendered = render_panel(p, _ctx_view(), _layout(), disabled=True)

    assert rendered is False
    assert p.draw_calls == []
    assert p.draw_disabled_calls == []


def test_render_panel_disabled_true_calls_draw_disabled_not_draw():
    """A panel implementing draw_disabled() renders it when disabled=True —
    and draw() must NOT be called. The whole point is that the inapplicable
    path never touches state draw() would read."""
    p = _real_panel("BothMethods", with_draw_disabled=True)
    rendered = render_panel(p, _ctx_view(), _layout(), disabled=True)

    assert rendered is True
    assert len(p.draw_disabled_calls) == 1
    assert p.draw_calls == []


# ---------------------------------------------------------------------------
# partition_panels — the (applies, disabled) superset of visible_panels
# ---------------------------------------------------------------------------


def test_partition_panels_splits_on_poll():
    applies_panel = _real_panel("Applies", poll=True)
    disabled_panel = _real_panel("Disabled", poll=False)

    applies, disabled = partition_panels([applies_panel, disabled_panel], _ctx_view())

    assert applies == [applies_panel]
    assert disabled == [disabled_panel]


def test_partition_panels_drops_access_denied_from_both_lists():
    """A panel denied by access= is dropped from BOTH lists — a greyed entry
    would advertise what the principal may not have (ADR-0029)."""
    denied = _real_panel("Denied", poll=True)
    denied.class_identity = PanelIdentity(
        registry_id="denied", registry_key="k:denied", label="Denied", access=AccessTier.ADMIN
    )

    ctx = MagicMock()
    ctx.can_access.return_value = False

    applies, disabled = partition_panels([denied], ctx)

    assert applies == []
    assert disabled == []


def test_partition_panels_preserves_registration_order_within_each_list():
    a = _real_panel("A", poll=True, order=10)
    b = _real_panel("B", poll=False, order=20)
    c = _real_panel("C", poll=True, order=30)
    d = _real_panel("D", poll=False, order=40)

    applies, disabled = partition_panels([a, b, c, d], _ctx_view())

    assert applies == [a, c]
    assert disabled == [b, d]


def test_partition_panels_interleaves_in_order_not_applies_then_disabled():
    """Confirmed real gap: hosts render both lists interleaved in `order`, not
    applies-then-disabled — otherwise a menu reshuffles as the selection
    changes. partition_panels itself returns two separate lists; this test
    proves what a host must do with them: merge by `order`, not concatenate."""
    applies_low = _real_panel("AppliesLow", poll=True, order=10)
    disabled_mid = _real_panel("DisabledMid", poll=False, order=20)
    applies_high = _real_panel("AppliesHigh", poll=True, order=30)
    disabled_low_order = _real_panel("DisabledLowOrder", poll=False, order=5)

    classes = [applies_low, disabled_mid, applies_high, disabled_low_order]
    applies, disabled = partition_panels(classes, _ctx_view())

    # A host merges both lists by order — exactly as BasePanel.render_surface
    # does (`sorted([...applies...] + [...disabled...], key=order)`).
    merged = sorted(
        [(cls, False) for cls in applies] + [(cls, True) for cls in disabled],
        key=lambda pair: pair[0].class_identity.order,
    )
    merged_names = [cls.__name__ for cls, _ in merged]

    # Interleaved by order, NOT applies-then-disabled (which would read
    # ["AppliesLow", "AppliesHigh", "DisabledLowOrder", "DisabledMid"]).
    assert merged_names == [
        "DisabledLowOrder",
        "AppliesLow",
        "DisabledMid",
        "AppliesHigh",
    ]
