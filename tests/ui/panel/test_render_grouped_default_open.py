"""_render_grouped threads default_open through hui.category_group so a
category named "advanced" renders collapsed by default (task-1-brief.md 1c).

hui.category_group itself already defaults to default_open=True — this test
guards the wiring in _render_grouped, i.e. that it computes and passes
default_open=(category.lower() != "advanced") rather than relying on
category_group's own default.
"""

from typing import Any, cast

import pytest

from nicegui import Client, ui
from nicegui.elements.expansion import Expansion

from haywire.core.settings import SettingsRegistry, setting
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.barn.builtin.types import STRING
from haywire.ui.panel.render_utils import render_schema

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _walk(element):
    """Depth-first walk over a NiceGUI element tree."""
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _expansion_open_by_category(anchor) -> dict[str, bool]:
    """Map category -> the ui.expansion.value found inside that category's
    data-category-group wrapper."""
    result: dict[str, bool] = {}
    for el in _walk(anchor):
        props = getattr(el, "_props", {})
        category = props.get("data-category-group")
        if category is None:
            continue
        for descendant in _walk(el):
            if isinstance(descendant, Expansion):
                result[category] = descendant.value
                break
    return result


class _DefaultOpenBag(FrameworkSettings, namespace="test.render_grouped_default_open"):
    network_field = setting[STRING]("n", label="Network Field", category="network", order=1)
    advanced_field = setting[STRING]("a", label="Advanced Field", category="advanced", order=2)
    upper_advanced_field = setting[STRING]("u", label="Upper Advanced", category="Advanced", order=3)
    other_field = setting[STRING]("o", label="Other Field", category="other", order=4)


@pytest.fixture
def registry() -> SettingsRegistry:
    reg = SettingsRegistry()
    reg.register_schema(_DefaultOpenBag)
    return reg


def test_advanced_category_renders_collapsed_by_default(registry: SettingsRegistry):
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_schema(_DefaultOpenBag, registry)

    open_by_category = _expansion_open_by_category(anchor)
    assert open_by_category["network"] is True
    assert open_by_category["advanced"] is False
    assert open_by_category["other"] is True


def test_advanced_category_match_is_case_insensitive(registry: SettingsRegistry):
    # A separate bag whose only category is "Advanced" (title case) still
    # collapses — category.lower() != "advanced" is the actual comparison.
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_schema(_DefaultOpenBag, registry)

    open_by_category = _expansion_open_by_category(anchor)
    # Both "advanced" and "Advanced" categories in this bag are collapsed —
    # the second, distinct wrapper is only reachable if groupby doesn't merge
    # non-consecutive categories, which _render_grouped already guarantees
    # (see render_schema's declaration-order contract).
    assert open_by_category.get("advanced") is False
    assert open_by_category.get("Advanced") is False
