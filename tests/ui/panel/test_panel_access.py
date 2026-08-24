"""access= enforcement in the single shared panel gate."""

from unittest.mock import MagicMock

from haywire.core.access import AccessTier
from haywire.ui.panel.base import BasePanel
from haywire.ui.panel.host_rendering import render_panel, visible_panels
from haywire.ui.panel.identity import PanelIdentity


def _panel(name: str, access: AccessTier, *, visible: bool = True):
    class _P(BasePanel):
        drew = False

        @classmethod
        def poll(cls, ctx):
            return visible

        def draw(self, ctx, layout):
            type(self).drew = True

    _P.__name__ = name
    _P.class_identity = PanelIdentity(registry_id=name, registry_key=f"k:{name}", label=name, access=access)
    return _P


def _panel_with_both_methods(name: str, access: AccessTier):
    """A panel implementing BOTH draw() and draw_disabled() — the asymmetry an
    author denied by access= will get wrong if only draw() is checked."""

    class _P(BasePanel):
        drew = False
        drew_disabled = False

        @classmethod
        def poll(cls, ctx):
            return True

        def draw(self, ctx, layout):
            type(self).drew = True

        def draw_disabled(self, ctx, layout):
            type(self).drew_disabled = True

    _P.__name__ = name
    _P.class_identity = PanelIdentity(registry_id=name, registry_key=f"k:{name}", label=name, access=access)
    return _P


def _ctx(tier: AccessTier):
    ctx = MagicMock()
    ctx.can_access.side_effect = lambda required: tier.satisfies(required)
    return ctx


def _layout():
    layout = MagicMock()
    layout.container = MagicMock()
    layout.container.__enter__ = MagicMock(return_value=layout.container)
    layout.container.__exit__ = MagicMock(return_value=False)
    return layout


def test_view_principal_sees_only_view_panels():
    panels = [
        _panel("ViewP", AccessTier.VIEW),
        _panel("EditP", AccessTier.EDIT),
        _panel("AdminP", AccessTier.ADMIN),
    ]
    kept = visible_panels(panels, _ctx(AccessTier.VIEW))
    assert [p.__name__ for p in kept] == ["ViewP"]


def test_edit_principal_sees_view_and_edit():
    panels = [
        _panel("ViewP", AccessTier.VIEW),
        _panel("EditP", AccessTier.EDIT),
        _panel("AdminP", AccessTier.ADMIN),
    ]
    kept = visible_panels(panels, _ctx(AccessTier.EDIT))
    assert [p.__name__ for p in kept] == ["ViewP", "EditP"]


def test_admin_sees_everything():
    panels = [
        _panel("ViewP", AccessTier.VIEW),
        _panel("EditP", AccessTier.EDIT),
        _panel("AdminP", AccessTier.ADMIN),
    ]
    assert len(visible_panels(panels, _ctx(AccessTier.ADMIN))) == 3


def test_access_is_checked_before_poll_is_even_called():
    """A denied panel's poll() must not run — it may read state the principal cannot see."""
    polled = []

    class _P(BasePanel):
        @classmethod
        def poll(cls, ctx):
            polled.append(True)
            return True

        def draw(self, ctx, layout): ...

    _P.class_identity = PanelIdentity(registry_id="p", registry_key="k", label="P", access=AccessTier.ADMIN)
    visible_panels([_P], _ctx(AccessTier.VIEW))
    assert polled == []


def test_poll_false_still_hides_an_accessible_panel():
    panel = _panel("Hidden", AccessTier.VIEW, visible=False)
    assert visible_panels([panel], _ctx(AccessTier.ADMIN)) == []


def test_a_panel_with_no_identity_is_treated_as_view():
    """Defensive: a hand-built test double without class_identity must not crash the host."""

    class _P(BasePanel):
        @classmethod
        def poll(cls, ctx):
            return True

        def draw(self, ctx, layout): ...

    assert visible_panels([_P], _ctx(AccessTier.VIEW)) == [_P]


def test_render_panel_refuses_a_denied_panel_even_without_poll_filtering():
    panel = _panel("AdminP", AccessTier.ADMIN)
    assert render_panel(panel, _ctx(AccessTier.VIEW), _layout()) is False
    assert panel.drew is False


def test_render_panel_draws_an_allowed_panel():
    panel = _panel("ViewP", AccessTier.VIEW)
    assert render_panel(panel, _ctx(AccessTier.ADMIN), _layout()) is True
    assert panel.drew is True


def test_render_panel_refuses_a_denied_panel_disabled_path_too():
    """access= denies BOTH draw() and draw_disabled() — a greyed entry would
    advertise what the principal may not have (ADR-0029). Confirmed real gap:
    the sibling test above only exercised the disabled=False (draw()) path;
    this is the asymmetry an author denied by access= would get wrong."""
    panel = _panel_with_both_methods("AdminBoth", AccessTier.ADMIN)
    assert render_panel(panel, _ctx(AccessTier.VIEW), _layout(), disabled=True) is False
    assert panel.drew is False
    assert panel.drew_disabled is False
