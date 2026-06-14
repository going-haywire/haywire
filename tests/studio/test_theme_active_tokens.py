"""The active-element highlight tokens must be emitted by shipped themes."""

import pytest

pytestmark = pytest.mark.unit


def test_shipped_themes_emit_active_tokens():
    from haybale_studio.themes.workbench import HaywireDarkTheme, HaywireLightTheme

    for theme_cls in (HaywireDarkTheme, HaywireLightTheme):
        css = theme_cls().to_css_vars()
        assert "--hw-node-active" in css, f"{theme_cls.__name__} missing --hw-node-active"
        assert "--hw-edge-active" in css, f"{theme_cls.__name__} missing --hw-edge-active"
        # active must differ from selected so the two tiers are distinguishable
        assert css["--hw-node-active"] != css["--hw-node-selected"]
