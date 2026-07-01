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
