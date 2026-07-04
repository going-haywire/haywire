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
