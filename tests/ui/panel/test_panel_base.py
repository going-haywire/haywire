# tests/ui/panel/test_panel_base.py
"""BasePanel base class: classmethod poll (default True); abstract draw."""

import pytest

from haywire.ui.panel import BasePanel


def test_panel_default_poll_returns_true():
    class P(BasePanel):
        def draw(self, ctx, layout, actions):
            pass

    assert P.poll(ctx=None) is True


def test_panel_subclass_can_override_poll():
    class P(BasePanel):
        @classmethod
        def poll(cls, ctx):
            return False

        def draw(self, ctx, layout, actions):
            pass

    assert P.poll(ctx=None) is False


def test_panel_draw_is_required():
    """Instantiating a BasePanel without draw should fail."""

    class P(BasePanel):
        pass

    with pytest.raises(TypeError, match="abstract"):
        P()


def test_panel_with_draw_can_be_instantiated():
    class P(BasePanel):
        def draw(self, ctx, layout, actions):
            pass

    instance = P()
    assert instance is not None
