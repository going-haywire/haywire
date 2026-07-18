"""watch() fields render as disabled (greyed) widgets, not label-only rows —
mirror-ness no longer forces a bespoke rendering path (Task 7). ui_state=
DISABLED is the general chrome mechanism (ADR 0020), applied uniformly."""

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


def _reset_enabled(row) -> bool:
    item = _menu_items(row).get("Reset to default") or _menu_items(row).get("Reset to global default")
    return item is not None and item.enabled


def _render(node, accessor="filter"):
    client = Client(_noop_page, request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(getattr(node, accessor))
    return anchor


def test_watch_field_renders_a_real_widget_not_a_label(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    anchor = _render(node)
    row = _find_field_row(anchor, "threshold_watched")
    assert row is not None
    # A real widget (NumberDrag for FLOAT) renders — not the plain-label fallback.
    assert any(getattr(el, "_props", {}).get("data-number_drag") is not None for el in _walk(row))


def test_watch_row_menu_offers_outlet_only(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    anchor = _render(node)
    row = _find_field_row(anchor, "threshold_watched")
    assert set(_menu_items(row)) == {"Promote to outlet", "Reset to global default"}
    assert not _reset_enabled(row), "clean row must grey reset"


def test_watch_row_suppresses_dirty_glyph_while_disabled(make_node_with_setting):
    """watch() fields are writable now — a local write marks them locally-set
    like any other mirror field (Reset lights up) — but watch() also seeds
    ui_state=DISABLED, and the • glyph is suppressed on any non-NORMAL row, so
    a greyed watch() field never shows the dirty marker."""
    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    node.filter.threshold_watched = 0.9
    anchor = _render(node)
    row = _find_field_row(anchor, "threshold_watched")
    texts = [getattr(el, "text", "") or "" for el in _walk(row)]
    assert not any(t.startswith("•") for t in texts)
    assert _reset_enabled(row) is False, "DISABLED row greys reset too, same UiState gate"


def test_unpromotable_watch_row_menu_has_reset_only(make_node_with_setting):
    """Reset is offered for every field regardless of promotability (Task 7) —
    it is no longer gated on _read_only, so an unpromotable watch() row still
    gets a menu, just with no promote entries."""
    from haywire.core.settings.descriptor import Promotable

    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    type(node.filter).__dict__["threshold_watched"]._promotable = Promotable.NONE

    anchor = _render(node)
    row = _find_field_row(anchor, "threshold_watched")
    assert set(_menu_items(row)) == {"Reset to global default"}


def test_promoted_watch_row_menu_swaps_to_demote(make_node_with_setting):
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    node = make_node_with_setting(accessor="filter", field="threshold", with_watch=True)
    promote_setting(node, "filter", "threshold_watched", direction=PortType.OUTLET)

    anchor = _render(node)
    row = _find_field_row(anchor, "threshold_watched")
    assert set(_menu_items(row)) == {"Demote", "Reset to global default"}
