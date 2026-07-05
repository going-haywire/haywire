"""The Properties row marks a promoted field as inlet-driven (data-promoted)."""

import haywire.core.graph.editor  # noqa: F401

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


def _find_promoted_hint(row) -> str | None:
    for el in _walk(row):
        props = getattr(el, "_props", {})
        if "data-promoted-hint" in props:
            return el.text
    return None


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

    client = Client(_noop_page, request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(node.filter)

    row = _find_field_row(anchor, "threshold")
    assert row is not None
    assert row._props.get("data-promoted-direction") == "inlet"
    hint = _find_promoted_hint(row)
    assert hint is not None and "promoted to inlet" in hint
    assert not _has_editable_widget(row), "promoted inlet must render read-only, no editable widget"


def test_promoted_linked_inlet_row_shows_driven_hint(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    desc = type(node.filter).__dict__["threshold"]
    pid = desc.storage_key
    port = node.ports[pid]
    port._linked_edges["fake_edge"] = object()  # is_linked() only checks length

    client = Client(_noop_page, request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(node.filter)

    row = _find_field_row(anchor, "threshold")
    assert row is not None
    assert row._props.get("data-promoted-direction") == "inlet"
    hint = _find_promoted_hint(row)
    assert hint is not None and "driven by inlet" in hint
    assert not _has_editable_widget(row), "promoted inlet must render read-only even when linked"


def test_promoted_outlet_row_stays_editable(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    promote_setting(node, "filter", "threshold", direction=PortType.OUTLET)

    client = Client(_noop_page, request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(node.filter)

    row = _find_field_row(anchor, "threshold")
    assert row is not None
    assert row._props.get("data-promoted-direction") == "outlet"
    hint = _find_promoted_hint(row)
    assert hint is not None and "promoted to outlet" in hint
    assert _has_editable_widget(row), "promoted outlet must keep its editable widget"


# --------------------------------------------------------------------------
# Reset / dirty chrome (• prefix + reset button) — decision Q1/Q2/Q3.
# Shown when a field is locally-set AND not owned by a promoted inlet; hidden
# otherwise. Applies to plain fields, not just mirror fields.
# --------------------------------------------------------------------------


def _find_reset_button(row):
    """Return the reset ``ui.button`` in *row* (icon ``restart_alt``), or None."""
    for el in _walk(row):
        if getattr(el, "_props", {}).get("icon") == "restart_alt":
            return el
    return None


def _reset_visible(row) -> bool:
    btn = _find_reset_button(row)
    return btn is not None and "hidden" not in getattr(btn, "_classes", [])


def _dirty_label(row) -> bool:
    """True if the field's label carries the • dirty prefix."""
    for el in _walk(row):
        text = getattr(el, "text", "") or ""
        if text.startswith("• "):
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


def test_pristine_plain_field_has_no_reset(make_node_with_setting):
    """An untouched, unpromoted plain field shows neither • nor a reset button."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    row = _render(node)
    assert row is not None
    assert not _reset_visible(row)
    assert not _dirty_label(row)


def test_locally_set_plain_field_shows_reset(make_node_with_setting):
    """Editing a plain field to a non-default value marks it locally-set, so the
    row shows the • prefix and a reset button (mirror gate removed — Q1)."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter.threshold = 0.9  # != default 0.5 -> _set_keys

    row = _render(node)
    assert row is not None
    assert _reset_visible(row)
    assert _dirty_label(row)


def test_reset_button_restores_default_and_clears_dirty(make_node_with_setting):
    """Clicking reset (via reset()) restores the default and clears the local
    opinion, so a re-render shows no • / reset."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    node.filter.threshold = 0.9
    assert node.filter.is_locally_set("threshold")

    node.filter.reset("threshold")
    assert node.filter.threshold == 0.5
    assert not node.filter.is_locally_set("threshold")

    row = _render(node)
    assert row is not None
    assert not _reset_visible(row)
    assert not _dirty_label(row)


def test_promoted_inlet_hides_reset_even_when_locally_set(make_node_with_setting):
    """A promoted inlet owns the value; promotion marks the field locally-set, but
    the read-only inlet row must NOT offer reset (Q3)."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")  # default direction = inlet
    assert node.filter.is_locally_set("threshold")

    row = _render(node)
    assert row is not None
    assert row._props.get("data-promoted-direction") == "inlet"
    assert not _reset_visible(row), "promoted inlet must hide reset"
    assert not _dirty_label(row)


def test_demoted_unchanged_field_is_dirty_then_reset_clears_it(make_node_with_setting):
    """Promote-then-demote leaves the field locally-set even if its value never
    changed (freeze-on-disconnect): the row shows • + reset. reset() then discards
    the local opinion — even though value == default and no cell event fires — so a
    re-render shows no chrome. This is the state behind the 'reset does nothing'
    report; the fix refreshes chrome directly from the click handler."""
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
    assert _reset_visible(row), "demoted-unchanged field is dirty (freeze-on-disconnect)"
    assert _dirty_label(row)

    # reset() discards the opinion despite old == new (no cell write / event).
    node.filter.reset("threshold")
    assert not node.filter.is_locally_set("threshold")
    assert node.filter.threshold == default

    row = _render(node)
    assert row is not None
    assert not _reset_visible(row), "after reset the row is pristine"
    assert not _dirty_label(row)


def test_reset_click_clears_chrome_in_place_without_cell_event(make_node_with_setting):
    """The live regression: for a locally-set field whose value already equals the
    default, clicking reset fires NO cell event (old == new), so the ONLY thing that
    clears the • / reset button is the handler refreshing its own row. Render once,
    click the reset button in place, assert the same elements clear — no re-render."""
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
        assert _reset_visible(row) and _dirty_label(row)

        _click(_find_reset_button(row))

        # Same DOM, refreshed in place — no _render() rebuild.
        assert not node.filter.is_locally_set("threshold")
        assert not _reset_visible(row), "reset click must hide the button in place"
        assert not _dirty_label(row), "reset click must drop the • prefix in place"


def test_promoted_outlet_keeps_reset_when_locally_set(make_node_with_setting):
    """A promoted outlet keeps the setting as source of truth (editable widget), so
    a locally-set outlet field still offers reset (Q3)."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    node.filter.threshold = 0.9
    promote_setting(node, "filter", "threshold", direction=PortType.OUTLET)

    row = _render(node)
    assert row is not None
    assert row._props.get("data-promoted-direction") == "outlet"
    assert _reset_visible(row), "promoted outlet must keep reset"
    assert _dirty_label(row)
