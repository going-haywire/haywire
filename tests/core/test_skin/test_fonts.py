"""One font list, shared by the annotation and widget-node skins."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_every_font_has_a_stack():
    from haywire.barn.builtin.nodes import annotation
    from haywire.core.skin import fonts

    assert set(fonts.FONT_STACKS) == set(fonts.FONTS)
    assert annotation.FONTS is fonts.FONTS
