"""The settings row's label/control split: half the row, capped at a maximum label width."""

import pytest

pytestmark = pytest.mark.unit


def test_the_split_rule_caps_half_the_row():
    from haywire.ui.app.shell import STATIC_CSS

    assert "width: min(50%, var(--hw-max-label-width, 9rem))" in STATIC_CSS
    assert "@container settings-panel" not in STATIC_CSS
