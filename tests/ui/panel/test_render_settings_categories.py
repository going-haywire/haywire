"""``render_settings(categories=...)`` — one slice of a bag, same rendering.

The slice exists so a surface that owns a subject (the toolbar's Appearance
dropdown) can show one category of a bag without a second renderer. What must
hold is that it is a *filter*: declaration order, category grouping and the
per-field chrome are whatever the unfiltered render produces, minus the rows
that were filtered out.
"""

from typing import Any, cast

import pytest

from nicegui import Client, ui

from haywire.barn.builtin.types import BOOL, INT, STRING
from haywire.core.settings import Settings, setting
from haywire.ui.panel.render_utils import render_settings

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _walk(element):
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _render(bag, **kwargs) -> "ui.column":
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(bag, **kwargs)
    return anchor


def _sequence(anchor) -> list[tuple[str, str]]:
    """("group", category) / ("field", attr_name) entries in DOM order."""
    out: list[tuple[str, str]] = []
    for el in _walk(anchor):
        props = getattr(el, "_props", {})
        group = props.get("data-category-group")
        field = props.get("data-field")
        if group is not None:
            out.append(("group", group))
        elif field:
            out.append(("field", field))
    return out


class _MixedBag(Settings):
    muted = setting[BOOL](False, category="state", order=10)
    skin = setting[STRING]("default", category="appearance", order=10)
    body_color = setting[STRING]("", category="appearance", order=20)
    comment = setting[STRING]("", category="annotation", order=10)
    pos_x = setting[INT](0, category="layout", order=10)


def test_only_the_named_category_renders():
    seq = _sequence(_render(_MixedBag(), categories=("appearance",)))
    assert seq == [("group", "appearance"), ("field", "skin"), ("field", "body_color")]


def test_several_categories_keep_declaration_order_not_argument_order():
    """Passing ("layout", "state") must not reorder anything: the filter never
    re-sorts, so state (declared first) still renders first."""
    seq = _sequence(_render(_MixedBag(), categories=("layout", "state")))
    assert seq == [
        ("group", "state"),
        ("field", "muted"),
        ("group", "layout"),
        ("field", "pos_x"),
    ]


def test_no_categories_argument_renders_everything():
    seq = _sequence(_render(_MixedBag()))
    fields = [name for kind, name in seq if kind == "field"]
    assert fields == ["muted", "skin", "body_color", "comment", "pos_x"]


def test_an_unknown_category_selects_nothing_rather_than_raising():
    seq = _sequence(_render(_MixedBag(), categories=("nonexistent",)))
    assert seq == []
