"""Override chrome (• dirty glyph + menu Reset item) on the REGISTRY row path.

``_render_field_row`` (render_schema / render_keys) carries the same chrome as
the reactive path, but over the registry's tier stack rather than a bag's local
opinion:

    workspace tier set  -> "overridden" (• + enabled Reset)
    reset               -> clear workspace, fall back to global tier or default

The menu item is worded from where a reset actually lands: "Reset to global
setting" when the global tier holds a value, "Reset to default" otherwise. The
global tier is hand-edited and never written by the app, so the app can only
ever clear the workspace tier.
"""

from typing import Any, cast

import pytest
from nicegui import Client, ui

from haywire.barn.builtin.types import STRING
from haywire.core.settings import SettingsRegistry, setting
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.ui.panel.render_utils import render_schema

pytestmark = pytest.mark.integration

KEY = "test.registry_reset.flavour"


def _noop_page() -> None:  # registration target for a headless Client
    pass


class _ResetBag(FrameworkSettings, namespace="test.registry_reset"):
    flavour = setting[STRING]("vanilla", label="Flavour")


@pytest.fixture
def registry() -> SettingsRegistry:
    reg = SettingsRegistry()
    reg.register_schema(_ResetBag)
    return reg


def _walk(element):
    """Depth-first walk over a NiceGUI element tree."""
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _menu_item_text(item) -> str:
    """A ui.menu_item's caption lives in a child label, not on the item."""
    for child in item.default_slot.children:
        text = getattr(child, "text", None)
        if text is not None:
            return text
    return ""


def _menu_items(row) -> dict[str, Any]:
    return {_menu_item_text(el): el for el in _walk(row) if type(el).__name__ == "MenuItem"}


def _reset_item(row):
    items = _menu_items(row)
    return items.get("Reset to default") or items.get("Reset to global setting")


def _dirty_label(row) -> bool:
    return any((getattr(el, "text", "") or "").startswith("• ") for el in _walk(row))


def _find_field_row(root, attr_name: str):
    for el in _walk(root):
        if getattr(el, "_props", {}).get("data-field") == attr_name:
            return el
    return None


def _render(registry: SettingsRegistry):
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_schema(_ResetBag, registry)
    return _find_field_row(anchor, "flavour")


def _click(item) -> None:
    """Fire a NiceGUI element's registered click handler headlessly."""
    listener_id = next(iter(item._event_listeners))
    item._handle_event({"listener_id": listener_id, "args": {}})


def test_pristine_row_lists_reset_but_greyed(registry: SettingsRegistry):
    """An untouched registry field lists Reset in its menu but disabled."""
    row = _render(registry)
    assert row is not None
    item = _reset_item(row)
    assert item is not None
    assert not item.enabled
    assert not _dirty_label(row)


def test_workspace_set_marks_row_dirty_and_enables_reset(registry: SettingsRegistry):
    registry.set_global(KEY, "chocolate", tier="workspace")

    row = _render(registry)
    assert row is not None
    assert _dirty_label(row)
    assert _reset_item(row).enabled


def test_global_tier_alone_is_not_dirty(registry: SettingsRegistry):
    """The global tier is the user's own default, not an override the UI made —
    it must not read as dirty, and reset must stay greyed."""
    registry.set_global(KEY, "strawberry", tier="global")

    row = _render(registry)
    assert row is not None
    assert not _dirty_label(row)
    assert not _reset_item(row).enabled


def test_reset_wording_follows_the_fallback(registry: SettingsRegistry):
    """Wording must name where a reset actually lands: the global tier when set,
    the descriptor default otherwise."""
    registry.set_global(KEY, "chocolate", tier="workspace")
    row = _render(registry)
    assert "Reset to default" in _menu_items(row)

    registry.set_global(KEY, "strawberry", tier="global")
    row = _render(registry)
    assert "Reset to global setting" in _menu_items(row)


def test_reset_click_falls_back_to_global_tier(registry: SettingsRegistry):
    """With both tiers set, reset clears ONLY the workspace tier and the value
    lands on the global one — the app never writes the hand-edited global tier."""
    registry.set_global(KEY, "strawberry", tier="global")
    registry.set_global(KEY, "chocolate", tier="workspace")
    assert registry.cell_for(KEY).get_value() == "chocolate"

    row = _render(registry)
    _click(_reset_item(row))

    assert not registry.get_global_tier(KEY, "workspace").is_set
    assert registry.get_global_tier(KEY, "global").value == "strawberry"
    assert registry.resolve(KEY) == ("strawberry", "global")
    assert registry.cell_for(KEY).get_value() == "strawberry"


def test_reset_click_falls_back_to_default_without_global(registry: SettingsRegistry):
    registry.set_global(KEY, "chocolate", tier="workspace")

    row = _render(registry)
    _click(_reset_item(row))

    assert registry.resolve(KEY) == ("vanilla", "default")
    assert registry.cell_for(KEY).get_value() == "vanilla"


def test_reset_click_clears_chrome_in_place(registry: SettingsRegistry):
    """Chrome must clear on the SAME elements, with no re-render."""
    registry.set_global(KEY, "chocolate", tier="workspace")
    row = _render(registry)
    assert _dirty_label(row)

    _click(_reset_item(row))

    assert not _dirty_label(row)
    assert not _reset_item(row).enabled


def test_reset_click_clears_chrome_when_value_does_not_move(registry: SettingsRegistry):
    """A workspace value EQUAL to the default fires no cell event on reset (old ==
    new), so only the handler refreshing its own row can clear the chrome."""
    registry.set_global(KEY, "vanilla", tier="workspace")  # == descriptor default
    row = _render(registry)
    assert _dirty_label(row), "workspace-set is dirty even at the default value"

    _click(_reset_item(row))

    assert not registry.get_global_tier(KEY, "workspace").is_set
    assert not _dirty_label(row)
    assert not _reset_item(row).enabled


def test_external_workspace_write_updates_chrome_live(registry: SettingsRegistry):
    """The row subscribes to its key, so another tab / a JSON reload setting the
    workspace tier lights the • and enables Reset without a redraw. The registry
    holds subscriptions as weakrefs — this also pins the closure's lifetime."""
    row = _render(registry)
    assert not _dirty_label(row)

    registry.set_global(KEY, "chocolate", tier="workspace")

    assert _dirty_label(row)
    assert _reset_item(row).enabled
