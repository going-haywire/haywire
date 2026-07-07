"""Read-only (watch) fields render live-value rows with an outlet-only menu (Q8)."""

import haywire.core.graph.editor  # noqa: F401

import pytest
from nicegui import Client, ui

from haywire.ui.panel.render_utils import render_settings

pytestmark = pytest.mark.integration


def _noop_page() -> None:
    pass


def _walk(element):
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _find_field_row(root, attr_name: str):
    for el in _walk(root):
        if getattr(el, "_props", {}).get("data-field") == attr_name:
            return el
    return None


def _menu_item_text(item) -> str:
    """A ``MenuItem`` carries no ``.text`` of its own — it holds an ``ItemSection``
    child (``TextElement``) that does. Headless equivalent of what a browser
    renders as the item's label."""
    for child in item.default_slot.children:
        text = getattr(child, "text", None)
        if text is not None:
            return text
    return ""


def _menu_items(row) -> dict[str, object]:
    return {_menu_item_text(el): el for el in _walk(row) if type(el).__name__ == "MenuItem"}


def _has_row_menu(row) -> bool:
    return any(type(el).__name__ == "ContextMenu" for el in _walk(row))


def _value_label_text(row) -> str | None:
    for el in _walk(row):
        props = getattr(el, "_props", {})
        if "data-value" in props:
            return props["data-value"]
    return None


def _render(node, accessor="filter"):
    client = Client(_noop_page, request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(getattr(node, accessor))
    return anchor


def test_watch_field_renders_readonly_value_row(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    anchor = _render(node)
    row = _find_field_row(anchor, "threshold_watched")
    assert row is not None, "read_only fields must render a row now (Q8)"
    assert _value_label_text(row) == "0.5"


def test_watch_row_reflects_value_on_rerender(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    node.filter.threshold = 0.9

    anchor = _render(node)
    row = _find_field_row(anchor, "threshold_watched")
    assert _value_label_text(row) == "0.9"


def test_watch_row_menu_offers_outlet_only_no_reset(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    anchor = _render(node)
    row = _find_field_row(anchor, "threshold_watched")
    assert set(_menu_items(row)) == {"Promote to outlet"}


def test_watch_row_never_shows_dirty_glyph(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    node.filter.threshold = 0.9
    anchor = _render(node)
    row = _find_field_row(anchor, "threshold_watched")
    for el in _walk(row):
        text = getattr(el, "text", "") or ""
        assert not text.startswith("•") and not text.startswith("→•")


def test_unpromotable_watch_row_has_no_menu(make_node_with_setting):
    from haywire.core.settings.descriptor import Promotable

    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    type(node.filter).__dict__["threshold_watched"]._promotable = Promotable.NONE

    anchor = _render(node)
    row = _find_field_row(anchor, "threshold_watched")
    assert not _has_row_menu(row), "zero possible actions -> no context menu at all (Q4)"


def test_promoted_watch_row_menu_swaps_to_demote(make_node_with_setting):
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    promote_setting(node, "filter", "threshold_watched", direction=PortType.OUTLET)

    anchor = _render(node)
    row = _find_field_row(anchor, "threshold_watched")
    assert set(_menu_items(row)) == {"Demote"}
