"""The backdrop-blur token must be emitted by shipped themes, with the
opaque/translucent asymmetry intact.

A backdrop blur behind an opaque card is invisible and costs 1.90x on
zoomed-out pan, so the dark theme sets "none" and only the light theme (whose
node_bg is translucent) asks for it. Per ADR-0030 a token missing from
_CSS_TOKEN_MAP emits nothing and fails silently, which is what this guards.
"""

import pytest

pytestmark = pytest.mark.unit


def test_shipped_themes_emit_backdrop_blur_token():
    from haybale_studio.themes.workbench import HaywireDarkTheme, HaywireLightTheme

    for theme_cls in (HaywireDarkTheme, HaywireLightTheme):
        css = theme_cls().to_css_vars()
        assert "--hw-node-backdrop-blur" in css, f"{theme_cls.__name__} missing --hw-node-backdrop-blur"


def test_dark_theme_asks_for_no_blur():
    from haybale_studio.themes.workbench import HaywireDarkTheme

    css = HaywireDarkTheme().to_css_vars()
    assert css["--hw-node-backdrop-blur"] == "none"


def test_light_theme_keeps_its_blur():
    from haybale_studio.themes.workbench import HaywireLightTheme

    css = HaywireLightTheme().to_css_vars()
    assert css["--hw-node-backdrop-blur"] == "blur(10px)"
