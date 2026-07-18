# tests/ui/widget/test_set_enabled.py
"""
BaseWidget.set_enabled(bool):

- root is a NiceGUI DisableableElement  -> Quasar :disable prop toggles
- root is a plain container element     -> design-guide §2.11 CSS is
  applied via style(add=) and — critically — REMOVED via style(remove=)
  (style("") does NOT clear on NiceGUI 3.x, which is why the pair exists)
- unrendered / cleaned-up widget        -> silent no-op

Real NiceGUI elements need a Client slot context, hence the integration
marker (same pattern as tests/ui/panel/test_promoted_row_state.py).
"""

# Per CLAUDE.md test trap: import editor before other haywire modules.

from typing import Any

import pytest
from nicegui import Client, ui

from haywire.ui.widget.base import BaseWidget
from tests.ui.widget._sync_fixtures import make_float_port

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


class _NumberRootWidget(BaseWidget):
    """Root is ui.number — a DisableableElement (Quasar :disable branch)."""

    def build(self) -> Any:
        return ui.number(value=0.0)


class _ContainerRootWidget(BaseWidget):
    """Root is a plain div — NOT disableable (CSS-fallback branch)."""

    def build(self) -> Any:
        with ui.element("div") as root:
            ui.number(value=0.0)
        return root


def _rendered(widget_cls) -> BaseWidget:
    w = widget_cls(make_float_port())
    client = Client(_noop_page, request=None)
    with client:
        w.render()
    return w


class TestQuasarBranch:
    def test_disable_sets_quasar_disable_prop(self):
        w = _rendered(_NumberRootWidget)
        w.set_enabled(False)
        assert w.ui_element._props.get("disable") is True

    def test_reenable_clears_quasar_disable_prop(self):
        w = _rendered(_NumberRootWidget)
        w.set_enabled(False)
        w.set_enabled(True)
        assert w.ui_element._props.get("disable") is False


class TestCssFallbackBranch:
    def test_disable_applies_211_style(self):
        w = _rendered(_ContainerRootWidget)
        w.set_enabled(False)
        style = w.ui_element._style
        assert style.get("opacity") == "0.5"
        assert style.get("pointer-events") == "none"

    def test_reenable_removes_211_style(self):
        w = _rendered(_ContainerRootWidget)
        w.set_enabled(False)
        w.set_enabled(True)
        style = w.ui_element._style
        assert "opacity" not in style
        assert "pointer-events" not in style


class TestLifecycleGuards:
    def test_set_enabled_before_render_is_a_noop(self):
        w = _NumberRootWidget(make_float_port())
        w.set_enabled(False)  # must not raise
        assert w.ui_element is None

    def test_set_enabled_after_cleanup_is_a_noop(self):
        w = _rendered(_NumberRootWidget)
        w.cleanup()
        w.set_enabled(False)  # must not raise
