"""
Declaration-order regression for render_schema (settings panel field ordering
spec, internals/superpowers/2026-07-18-settings-panel-ordering-spec.md).

render_schema must walk schema_cls._property_settings() directly (declaration
order), filtering to only registry-known keys, WITHOUT re-sorting by
(category, order, setting_key). render_keys is explicitly unchanged — it keeps
sorting by (category, order, setting_key) because it aggregates keys across
independent classes with no shared declaration sequence.
"""

from typing import Any, cast

import pytest

from nicegui import Client, ui

from haywire.core.settings import SettingsRegistry, setting
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.barn.builtin.types import STRING
from haywire.ui.panel.render_utils import render_schema, render_keys

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _walk(element):
    """Depth-first walk over a NiceGUI element tree."""
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _dom_sequence(anchor) -> list[tuple[str, str]]:
    """Walk the rendered tree in DOM order, returning one entry per element
    that carries EITHER a data-category-group or a data-field prop, tagged
    ("group", category) or ("field", attr_name) respectively — in the exact
    order they appear."""
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


class _SchemaOrderingBag(FrameworkSettings, namespace="test.schema_ordering"):
    """Same declared-vs-order= mismatch shape as Task 2's _OrderingBag, but as
    a registry-backed FrameworkSettings schema (render_schema's actual input
    shape) instead of a plain Settings instance."""

    zebra = setting[STRING]("z", label="Zebra", category="z", order=5)
    apple = setting[STRING]("a", label="Apple", category="a", order=1)
    mango = setting[STRING]("m", label="Mango", category="a", order=4)
    banana = setting[STRING]("b", label="Banana", category="b", order=2)
    kiwi = setting[STRING]("k", label="Kiwi", category="a", order=3)


@pytest.fixture
def registry() -> SettingsRegistry:
    reg = SettingsRegistry()
    reg.register_schema(_SchemaOrderingBag)
    return reg


def test_schema_fields_render_in_declaration_order(registry: SettingsRegistry):
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_schema(_SchemaOrderingBag, registry)

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
    ], f"expected declaration-order rendering (z, a-block-1, b, a-block-2), got {sequence}"


class _KeysUnchangedBagAlpha(FrameworkSettings, namespace="test.keys_unchanged.alpha"):
    z_field = setting[STRING]("z", label="Z Field", category="shared", order=2)
    a_field = setting[STRING]("a", label="A Field", category="shared", order=1)


def test_render_keys_still_sorts_by_order_not_declaration():
    """Sentinel: render_keys is explicitly OUT of this migration's scope. Its
    merged, cross-class view must still sort by (category, order, key) —
    a_field (order=1) before z_field (order=2), even though z_field is
    DECLARED first. If this test ever fails, someone accidentally changed
    render_keys — see the spec's "Why the split" section for why it must not."""
    reg = SettingsRegistry()
    reg.register_schema(_KeysUnchangedBagAlpha)

    client = Client(cast(Any, _noop_page), request=None)
    with client:
        anchor = ui.column()
        with anchor:
            render_keys("test.keys_unchanged.alpha", reg)

    sequence = _dom_sequence(anchor)
    field_order = [name for kind, name in sequence if kind == "field"]
    assert field_order == ["a_field", "z_field"], (
        f"render_keys must sort by order= (a_field=1 before z_field=2), "
        f"NOT declaration order (z_field declared first), got {field_order}"
    )
