# tests/ui/panel/test_panel_base.py
"""Panel base class: classmethod poll (default True); abstract draw."""

import pytest

from haywire.ui.panel import Panel


def test_panel_default_poll_returns_true():
    class P(Panel):
        def draw(self, ctx, layout, actions):
            pass

    assert P.poll(ctx=None) is True


def test_panel_subclass_can_override_poll():
    class P(Panel):
        @classmethod
        def poll(cls, ctx):
            return False

        def draw(self, ctx, layout, actions):
            pass

    assert P.poll(ctx=None) is False


def test_panel_draw_is_required():
    """Instantiating a Panel without draw should fail."""

    class P(Panel):
        pass

    with pytest.raises(TypeError, match="abstract"):
        P()


def test_panel_with_draw_can_be_instantiated():
    class P(Panel):
        def draw(self, ctx, layout, actions):
            pass

    instance = P()
    assert instance is not None
