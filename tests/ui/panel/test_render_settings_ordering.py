"""
Declaration-order regression for render_settings (settings panel field ordering
spec, internals/superpowers/2026-07-18-settings-panel-ordering-spec.md).

render_settings must lay out fields in class-body declaration order (base-first
MRO walk, same order Settings._property_settings() yields) — NOT sorted by
category name or by the order= kwarg. Categories are not pre-grouped: the first
time a category name is seen a new section opens; a later, non-consecutive
occurrence of that same category name opens a SECOND, separate section (the
accepted "interleaved categories split into two blocks" tradeoff).
"""

import pytest

from nicegui import Client, ui

from haywire.core.settings import Settings, setting
from haywire.barn.builtin.types import BOOL, INT, STRING
from haywire.ui.panel.render_utils import render_settings

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _walk(element):
    """Depth-first walk over a NiceGUI element tree."""
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _render(bag) -> "ui.column":
    client = Client(_noop_page, request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_settings(bag)
    return anchor


def _dom_sequence(anchor) -> list[tuple[str, str]]:
    """Walk the rendered tree in DOM order, returning one entry per element
    that carries EITHER a data-category-group or a data-field prop, tagged
    ("group", category) or ("field", attr_name) respectively — in the exact
    order they appear. A category re-opened after being interrupted by
    another shows up as a second, separate ("group", ...) entry."""
    sequence: list[tuple[str, str]] = []
    for el in _walk(anchor):
        props = getattr(el, "_props", {})
        group = props.get("data-category-group")
        field = props.get("data-field")
        if group is not None:
            sequence.append(("group", group))
        elif field:
            sequence.append(("field", field))
    return sequence


class _OrderingBag(Settings):
    """Deliberately out-of-alphabetical-order, out-of-`order=`-order fields.

    Declaration sequence is: zebra(cat=z), apple(cat=a), mango(cat=a), banana
    (cat=b), kiwi(cat=a). If ordering were alphabetical-by-category this would
    render a, a, a, b, z; if it were sorted by `order=` it would render
    apple(1), banana(2), kiwi(3), mango(4), zebra(5) all interleaved by number.
    Declaration order must instead render: zebra, [apple, mango] (block 1 of
    "a"), banana, kiwi (block 2 of "a", a NEW section because "b" interrupted
    the first "a" run).
    """

    zebra = setting[STRING]("z", label="Zebra", category="z", order=5)
    apple = setting[STRING]("a", label="Apple", category="a", order=1)
    mango = setting[STRING]("m", label="Mango", category="a", order=4)
    banana = setting[STRING]("b", label="Banana", category="b", order=2)
    kiwi = setting[STRING]("k", label="Kiwi", category="a", order=3)


def test_fields_render_in_declaration_order_not_alphabetical_or_order_kwarg():
    bag = _OrderingBag()
    anchor = _render(bag)

    sequence = _dom_sequence(anchor)
    assert sequence == [
        ("group", "z"),
        ("field", "zebra"),
        ("group", "a"),
        ("field", "apple"),
        ("field", "mango"),
        ("group", "b"),
        ("field", "banana"),
        ("group", "a"),
        ("field", "kiwi"),
    ], (
        f"expected pure declaration order (z, then a-block-1 with apple+mango, "
        f"then b, then a SECOND a-block with just kiwi) — not order= or "
        f"alphabetical category sort — got {sequence}"
    )


class _RootFirstBag(Settings):
    """root-category field declared SECOND — must NOT jump to the front.

    Confirms the spec's "drop the root-first special case entirely" decision:
    unlike render_keys, render_settings gives root no positional privilege.
    """

    first = setting[BOOL](True, label="First", category="alpha")
    second = setting[BOOL](True, label="Second", category="root")


def test_root_category_does_not_sort_first():
    bag = _RootFirstBag()
    anchor = _render(bag)

    sequence = _dom_sequence(anchor)
    # root renders via hui.category_group's plain-column branch (no header,
    # no data-category-group wrapper prop distinct from any other category's
    # wrapper div — the wrapper div itself still carries data-category-group
    # for every category, "root" included, per _render_grouped).
    assert sequence == [
        ("group", "alpha"),
        ("field", "first"),
        ("group", "root"),
        ("field", "second"),
    ], f"root must render at its declared position (second), not first, got {sequence}"


class _BaseBag(Settings):
    base_field = setting[INT](1, label="Base Field", category="shared")


class _SubBag(_BaseBag):
    """Subclass field must render AFTER the inherited base field (base-first
    MRO walk, matching _property_settings())."""

    sub_field = setting[INT](2, label="Sub Field", category="shared")


def test_subclass_fields_render_after_base_fields():
    bag = _SubBag()
    anchor = _render(bag)

    sequence = _dom_sequence(anchor)
    assert sequence == [
        ("group", "shared"),
        ("field", "base_field"),
        ("field", "sub_field"),
    ]
