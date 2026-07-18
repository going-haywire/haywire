"""The Properties row marks a promoted field as inlet-driven (data-promoted)."""

import pytest
from nicegui import Client, ui
from nicegui import app as _app  # noqa: F401

from haywire.ui.panel.render_utils import render_settings

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _walk(element):
    """Depth-first walk over a NiceGUI element tree."""
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _has_promoted_marker(root) -> bool:
    for el in _walk(root):
        props = getattr(el, "_props", {})
        if props.get("data-promoted") == "true":
            return True
    return False


def test_promoted_field_row_is_marked(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")

    client = Client(_noop_page, request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(node.filter)

    assert _has_promoted_marker(anchor), "promoted row must carry data-promoted=true"


def test_unpromoted_field_row_is_not_marked(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")

    client = Client(_noop_page, request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(node.filter)

    assert not _has_promoted_marker(anchor), "unpromoted row must not be marked"


def _find_field_row(root, attr_name: str):
    """Find the ``ui.row`` element carrying ``data-field="<attr_name>"``."""
    for el in _walk(root):
        props = getattr(el, "_props", {})
        if props.get("data-field") == attr_name:
            return el
    return None


def _row_hint(row) -> str | None:
    """The row-level data-hint prop (promotion hint), or None."""
    return getattr(row, "_props", {}).get("data-hint")


def _find_promoted_label(row):
    """The literal 'promoted' widget-column label on an inlet row, or None."""
    for el in _walk(row):
        if "data-promoted-hint" in getattr(el, "_props", {}):
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
    """Map of menu-item text -> MenuItem element inside the row's context menu."""
    return {_menu_item_text(el): el for el in _walk(row) if type(el).__name__ == "MenuItem"}


def _has_row_menu(row) -> bool:
    return any(type(el).__name__ == "ContextMenu" for el in _walk(row))


def _reset_enabled(row) -> bool:
    item = _menu_items(row).get("Reset to default") or _menu_items(row).get("Reset to global default")
    return item is not None and item.enabled


def _has_editable_widget(row) -> bool:
    """An editable widget renders inside a ``sf-widget`` div WITHOUT a
    ``data-value`` prop (the read-only label fallback carries ``data-value``)."""
    for el in _walk(row):
        classes = getattr(el, "_classes", [])
        if "sf-widget" in classes:
            props = getattr(el, "_props", {})
            if "data-value" not in props:
                return True
    return False


def test_promoted_unlinked_inlet_row_is_read_only(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")

    row = _render(node)
    assert row is not None
    assert row._props.get("data-promoted-direction") == "inlet"
    assert _row_hint(row) == "promoted to inlet"
    assert not _has_editable_widget(row), "promoted inlet must render read-only, no editable widget"
    lbl = _find_promoted_label(row)
    assert lbl is not None and lbl.text == "promoted"


def test_promoted_linked_inlet_row_shows_driven_hint(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    desc = type(node.filter).__dict__["threshold"]
    port = node.ports[desc.storage_key]
    port._linked_edges["fake_edge"] = object()  # is_linked() only checks length

    row = _render(node)
    assert row is not None
    assert _row_hint(row) == "driven by inlet"
    assert not _has_editable_widget(row), "promoted inlet must render read-only even when linked"


def test_promoted_outlet_row_stays_editable(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    promote_setting(node, "filter", "threshold", direction=PortType.OUTLET)

    row = _render(node)
    assert row is not None
    assert row._props.get("data-promoted-direction") == "outlet"
    assert _row_hint(row) == "promoted to outlet"
    assert _has_editable_widget(row), "promoted outlet must keep its editable widget"
    assert _find_promoted_label(row) is None


def test_promoted_outlet_keeps_reset_when_locally_set(make_node_with_setting):
    """Outlet keeps the setting as source of truth: its menu Reset stays enabled,
    but the • dirty glyph is suppressed for any promotion direction (noise on a
    row the user can't act on the same way as an unpromoted field)."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    node.filter.threshold = 0.9
    promote_setting(node, "filter", "threshold", direction=PortType.OUTLET)

    row = _render(node)
    assert row is not None
    assert _reset_enabled(row), "promoted outlet must keep reset actionable"
    assert not _dirty_label(row)


# --------------------------------------------------------------------------
# Reset / dirty chrome (• prefix + menu Reset item) — decision Q1/Q2/Q3.
# Reset is shown when a field is locally-set AND not owned by a promoted
# inlet; hidden otherwise. Applies to plain fields, not just mirror fields.
# The • dirty glyph is narrower still: suppressed whenever the field is
# promoted (any direction) or its effective UiState is not NORMAL.
# --------------------------------------------------------------------------


def _dirty_label(row) -> bool:
    """True if the field's label carries the • dirty glyph."""
    for el in _walk(row):
        text = getattr(el, "text", "") or ""
        if text.startswith("• ") or text.startswith("→• "):
            return True
    return False


def _render(node):
    client = Client(_noop_page, request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(node.filter)
    return _find_field_row(anchor, "threshold")


def _click(button) -> None:
    """Fire a NiceGUI element's registered click handler headlessly."""
    listener_id = next(iter(button._event_listeners))
    button._handle_event({"listener_id": listener_id, "args": {}})


def test_pristine_plain_field_has_reset_disabled(make_node_with_setting):
    """An untouched field lists Reset in its menu but greyed (Q4: transient disables)."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    row = _render(node)
    assert row is not None
    assert "Reset to default" in _menu_items(row)
    assert not _reset_enabled(row)
    assert not _dirty_label(row)


def test_locally_set_plain_field_enables_reset(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter.threshold = 0.9  # != default 0.5 -> _set_keys

    row = _render(node)
    assert row is not None
    assert _reset_enabled(row)
    assert _dirty_label(row)


def test_reset_restores_default_and_clears_dirty(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter.threshold = 0.9
    node.filter.reset("threshold")
    assert node.filter.threshold == 0.5

    row = _render(node)
    assert row is not None
    assert not _reset_enabled(row)
    assert not _dirty_label(row)


def test_promoted_inlet_disables_reset_even_when_locally_set(make_node_with_setting):
    """Promotion marks the field locally-set, but the graph owns an inlet's value (Q5/Q4)."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    assert node.filter.is_locally_set("threshold")

    row = _render(node)
    assert row is not None
    assert not _reset_enabled(row), "promoted inlet must grey reset"
    assert not _dirty_label(row)


def test_demoted_unchanged_field_is_dirty_then_reset_clears_it(make_node_with_setting):
    """Promote-then-demote leaves the field locally-set even if its value never
    changed (freeze-on-disconnect): the row shows • + an enabled Reset item. reset()
    then discards the local opinion — even though value == default and no cell event
    fires — so a re-render shows no chrome. This is the state behind the 'reset does
    nothing' report; the fix refreshes chrome directly from the click handler."""
    from haywire.core.node.promotion import demote_setting, promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    default = node.filter.threshold  # 0.5, untouched

    promote_setting(node, "filter", "threshold")  # marks locally-set, value unchanged
    pid = type(node.filter).__dict__["threshold"].storage_key
    demote_setting(node, pid)

    # Locally-set, but value still equals the default: the "inert reset" case.
    assert node.filter.is_locally_set("threshold")
    assert node.filter.threshold == default

    row = _render(node)
    assert row is not None
    assert _reset_enabled(row), "demoted-unchanged field is dirty (freeze-on-disconnect)"
    assert _dirty_label(row)

    # reset() discards the opinion despite old == new (no cell write / event).
    node.filter.reset("threshold")
    assert not node.filter.is_locally_set("threshold")
    assert node.filter.threshold == default

    row = _render(node)
    assert row is not None
    assert not _reset_enabled(row), "after reset the row is pristine"
    assert not _dirty_label(row)


def test_reset_click_clears_chrome_in_place_without_cell_event(make_node_with_setting):
    """The live regression: for a locally-set field whose value already equals the
    default, clicking reset fires NO cell event (old == new), so the ONLY thing that
    clears the • / reset item is the handler refreshing its own row. Render once,
    click the reset menu item in place, assert the same elements clear — no re-render."""
    from haywire.core.node.promotion import demote_setting, promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")

    promote_setting(node, "filter", "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key
    demote_setting(node, pid)
    assert node.filter.is_locally_set("threshold")

    client = Client(_noop_page, request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(node.filter)

        row = _find_field_row(anchor, "threshold")
        assert row is not None
        assert _reset_enabled(row) and _dirty_label(row)

        _click(_menu_items(row)["Reset to default"])

        # Same DOM, refreshed in place — no _render() rebuild.
        assert not node.filter.is_locally_set("threshold")
        assert not _reset_enabled(row), "reset click must grey the item in place"
        assert not _dirty_label(row), "reset click must drop the • prefix in place"


# --------------------------------------------------------------------------
# Setting-row context menu (Q1/Q2/Q4/Q5/Q9) — the sole promote surface.
# --------------------------------------------------------------------------


def test_unpromoted_row_menu_offers_both_directions(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    row = _render(node)
    items = _menu_items(row)
    assert set(items) == {
        "Promote to inlet",
        "Promote to outlet",
        "Promote to config",
        "Reset to default",
    }


def test_promoted_row_menu_swaps_to_demote(make_node_with_setting):
    from haywire.core.node.promotion import promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold")
    row = _render(node)
    items = _menu_items(row)
    assert set(items) == {"Demote", "Reset to default"}


def test_menu_promote_click_promotes_inlet(make_node_with_setting):
    from haywire.core.node.promotion import is_field_promoted

    node = make_node_with_setting(accessor="filter", field="threshold")
    row = _render(node)
    _click(_menu_items(row)["Promote to inlet"])

    assert is_field_promoted(node.filter, "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert pid in node.ports and node.ports[pid].is_inlet()


def test_menu_promote_click_promotes_outlet(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    row = _render(node)
    _click(_menu_items(row)["Promote to outlet"])

    pid = type(node.filter).__dict__["threshold"].storage_key
    assert pid in node.ports and not node.ports[pid].is_inlet()


def test_menu_demote_click_demotes(make_node_with_setting):
    from haywire.core.node.promotion import is_field_promoted, promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold")
    row = _render(node)
    _click(_menu_items(row)["Demote"])

    assert not is_field_promoted(node.filter, "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert pid not in node.ports


def test_promotable_none_row_menu_has_reset_only(make_node_with_setting):
    from haywire.core.settings.descriptor import Promotable

    node = make_node_with_setting(accessor="filter", field="threshold")
    type(node.filter).__dict__["threshold"]._promotable = Promotable.NONE

    row = _render(node)
    assert set(_menu_items(row)) == {"Reset to default"}


def test_nodeless_bag_menu_has_reset_only(make_node_with_setting):
    """A bag without a node (e.g. GraphRunSettings) structurally hides promotion."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter._node = None

    row = _render(node)
    assert set(_menu_items(row)) == {"Reset to default"}


def test_disabled_row_greys_reset_but_keeps_promote_active(make_node_with_setting):
    """ADR 0020: chrome-locked, not value-locked — promote stays, reset follows the lock."""
    from haywire.core.settings import UiState

    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter.threshold = 0.9  # dirty — reset would be enabled if NORMAL
    node.filter.set_ui_state("threshold", UiState.DISABLED)

    row = _render(node)
    items = _menu_items(row)
    assert items["Promote to inlet"].enabled
    assert items["Promote to outlet"].enabled
    assert not _reset_enabled(row)


def test_label_glyph_grammar(make_node_with_setting):
    """Pristine: 'threshold' — dirty: '• threshold' — inlet: '→ threshold' —
    outlet (unedited): '→ threshold' — outlet (+dirty): '→ threshold'.

    The • dirty glyph is suppressed for ANY promoted field, regardless of
    direction — a promoted row (inlet or outlet) isn't something the plain
    "locally overridden, click Reset" affordance applies to in the same way,
    so the glyph would just be noise. The → promotion arrow alone conveys
    the row's special status."""
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    def _label_of(row) -> str:
        for el in _walk(row):
            classes = getattr(el, "_classes", [])
            if "sf-label" in classes:
                for child in _walk(el):
                    text = getattr(child, "text", None)
                    if text:
                        return text
        raise AssertionError("no label found")

    node = make_node_with_setting(accessor="filter", field="threshold")
    assert _label_of(_render(node)) == "threshold"

    node.filter.threshold = 0.9
    assert _label_of(_render(node)) == "• threshold"

    node2 = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node2, "filter", "threshold")  # inlet: locally-set but graph-owned -> no •
    assert _label_of(_render(node2)) == "→ threshold"

    node3 = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node3, "filter", "threshold", direction=PortType.OUTLET)
    assert _label_of(_render(node3)) == "→ threshold"  # unedited outlet -> no •

    node3.filter.threshold = 0.9  # written through the normal panel/registry path
    assert _label_of(_render(node3)) == "→ threshold"  # still promoted -> no •


def test_promoted_config_row_is_read_only(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    promote_setting(node, "filter", "threshold", direction=PortType.CONFIG)

    row = _render(node)
    assert row is not None
    assert row._props.get("data-promoted-direction") == "config"
    assert _row_hint(row) == "promoted to config"
    assert not _has_editable_widget(row), "promoted config must render read-only, no editable widget"
    lbl = _find_promoted_label(row)
    assert lbl is not None and lbl.text == "promoted"


def test_promoted_config_row_reset_is_meaningless(make_node_with_setting):
    """Same as a promoted inlet: the row is read-only, so Reset is meaningless
    even if the field carries a local opinion."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    node.filter.threshold = 0.9
    promote_setting(node, "filter", "threshold", direction=PortType.CONFIG)

    row = _render(node)
    assert row is not None
    assert not _reset_enabled(row), "promoted config row's Reset must stay disabled, same as inlet"


def test_config_eligible_field_offers_promote_to_config_menu_entry(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")

    row = _render(node)
    assert row is not None
    items = _menu_items(row)
    assert "Promote to config" in items, "an unpromoted, CONFIG-eligible field must offer Promote to config"
