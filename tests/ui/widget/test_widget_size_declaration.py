"""A widget's declared size box: ``@widget(min_width=, min_height=, max_height=)``.

Declaring a size box opts a widget out of content-driven intrinsic sizing — its
contents stop contributing to the node's size floor, so the resize gadget can
shrink the node past its content (an image viewer's natural pixel size, say)
down to the declared box. ``min_width`` alone contains the inline axis and lets
aspect-ratio content keep growing proportionally; adding ``min_height`` contains
both. See ``docs/components/widgets/widget-canon.md`` and the CSS contract in
``canvas.vue``.

The browser-side proof that the floor actually drops lives in
``tests/ui/harness/test_widget_size_box.py``; these are the Python-side plumbing
tests (declaration -> resolution -> stamped element).
"""

import dataclasses

from typing import Any, cast

import pytest

from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget
from haywire.ui.widget.identity import WidgetIdentity
from haywire.ui.widget.interface import IWidget
from haywire.ui.widget.sizing import (
    BOX_ATTR,
    INLINE_BOX_ATTR,
    MAX_HEIGHT_ATTR,
    stamp_size_declaration,
)


class _StubPort:
    """Minimal WidgetModel stand-in — BaseWidget only reads id/widget_config here."""

    def __init__(self, widget_config: dict | None = None) -> None:
        self.id = "port-1"
        self.widget_config = widget_config or {}


# ---------------------------------------------------------------------------
# Declaration — the @widget decorator carries the box onto WidgetIdentity
# ---------------------------------------------------------------------------


def test_identity_declares_size_fields_defaulting_to_none():
    field_names = {f.name for f in dataclasses.fields(WidgetIdentity)}
    assert {"min_width", "min_height", "max_height"} <= field_names

    @widget(description="stock widget, sizes from content")
    class Stock(BaseWidget):
        def build(self):
            return None

    assert Stock.class_identity.min_width is None
    assert Stock.class_identity.min_height is None
    assert Stock.class_identity.max_height is None


def test_decorator_carries_declared_box_onto_identity():
    @widget(description="viewer", min_width=160, min_height=90, max_height=400)
    class Viewer(BaseWidget):
        def build(self):
            return None

    assert Viewer.class_identity.min_width == 160
    assert Viewer.class_identity.min_height == 90
    assert Viewer.class_identity.max_height == 400


# ---------------------------------------------------------------------------
# Resolution — call-site config() overrides the class declaration
# ---------------------------------------------------------------------------


@widget(description="declares a box", min_width=160, min_height=90)
class _BoxedWidget(BaseWidget):
    def build(self):
        return None


@widget(description="declares nothing")
class _PlainWidget(BaseWidget):
    def build(self):
        return None


def test_resolution_falls_back_to_the_class_declaration():
    w = _BoxedWidget(cast(Any, _StubPort()))
    assert w.min_width == 160
    assert w.min_height == 90
    assert w.max_height is None


def test_call_site_config_overrides_the_class_declaration():
    port = _StubPort({"min_width": 320, "max_height": 250})
    w = _BoxedWidget(cast(Any, port))
    assert w.min_width == 320  # overridden at the call site
    assert w.min_height == 90  # untouched keys keep the class value
    assert w.max_height == 250  # declared only at the call site


def test_undeclared_widget_resolves_to_none():
    w = _PlainWidget(cast(Any, _StubPort()))
    assert w.min_width is None
    assert w.min_height is None
    assert w.max_height is None


def test_config_classmethod_round_trips_the_box():
    cfg = _BoxedWidget.config(min_width=320)
    w = _BoxedWidget(cast(Any, _StubPort(cfg["config"])))
    assert w.min_width == 320


@pytest.mark.parametrize("field", ["min_width", "min_height", "max_height"])
def test_non_integer_declaration_is_rejected(field):
    """A CSS px value — a str would silently emit `--hw-...: 160pxpx`."""
    w = _BoxedWidget(cast(Any, _StubPort({field: "160px"})))
    with pytest.raises(TypeError, match=field):
        getattr(w, field)


# ---------------------------------------------------------------------------
# Stamping — declaration reaches the DOM as custom props + marker attributes
# ---------------------------------------------------------------------------


class _StubElement:
    """Records what the stamp writes, without a NiceGUI client/slot."""

    def __init__(self) -> None:
        self._props: dict = {}
        self.styles: list[str] = []

    def style(self, decls: str) -> "_StubElement":
        self.styles.append(decls)
        return self


def test_stamp_writes_custom_props_and_box_marker():
    el = _StubElement()
    stamp_size_declaration(cast(Any, el), _BoxedWidget(cast(Any, _StubPort())))

    assert el._props[BOX_ATTR]
    style = "; ".join(el.styles)
    assert "--hw-widget-min-width: 160px" in style
    assert "--hw-widget-min-height: 90px" in style


def test_stamp_is_a_noop_for_an_undeclared_widget():
    el = _StubElement()
    stamp_size_declaration(cast(Any, el), _PlainWidget(cast(Any, _StubPort())))

    assert el._props == {}
    assert el.styles == []


def test_max_height_stamps_independently_of_the_box():
    el = _StubElement()
    stamp_size_declaration(cast(Any, el), _PlainWidget(cast(Any, _StubPort({"max_height": 250}))))

    assert MAX_HEIGHT_ATTR in el._props
    assert BOX_ATTR not in el._props  # ceiling and intrinsic box are separate knobs
    assert "--hw-widget-max-height: 250px" in "; ".join(el.styles)


def test_width_only_declaration_contains_the_inline_axis():
    """min_width alone is a valid, distinct mode — the block axis stays content-driven
    so aspect-ratio content keeps growing proportionally."""
    el = _StubElement()
    stamp_size_declaration(cast(Any, el), _PlainWidget(cast(Any, _StubPort({"min_width": 160}))))

    assert el._props[INLINE_BOX_ATTR]
    assert BOX_ATTR not in el._props
    style = "; ".join(el.styles)
    assert "--hw-widget-min-width: 160px" in style
    assert "--hw-widget-min-height" not in style


def test_height_only_declaration_is_ignored_and_warned(caplog):
    """CSS can contain the inline axis alone, but has no block-axis equivalent."""
    el = _StubElement()
    with caplog.at_level("WARNING"):
        stamp_size_declaration(cast(Any, el), _PlainWidget(cast(Any, _StubPort({"min_height": 90}))))

    assert BOX_ATTR not in el._props
    assert INLINE_BOX_ATTR not in el._props
    assert el.styles == []
    assert "min_width" in caplog.text


def test_stamp_tolerates_a_headless_element():
    stamp_size_declaration(cast(Any, None), _BoxedWidget(cast(Any, _StubPort())))  # must not raise


# ---------------------------------------------------------------------------
# The contract lives on IWidget, not BaseWidget
# ---------------------------------------------------------------------------


def test_a_bare_iwidget_implementation_carries_the_declaration():
    """Both halves of the declaration are IWidget-level state — the class default
    is class_identity, the override is what config() produces — so an
    implementation that skips BaseWidget still gets a size box, and the render
    path needs no isinstance narrowing."""

    @widget(description="bypasses BaseWidget entirely", min_width=200, min_height=120)
    class Bare(IWidget):
        def __init__(self, element):
            self.port = element

        def render(self):
            return None

    el = _StubElement()
    stamp_size_declaration(cast(Any, el), Bare(_StubPort()))

    assert el._props[BOX_ATTR]
    style = "; ".join(el.styles)
    assert "--hw-widget-min-width: 200px" in style
    assert "--hw-widget-min-height: 120px" in style


def test_a_bare_iwidget_implementation_has_no_call_site_overrides():
    """_size_overrides() defaults to empty: no stored config, no override layer."""

    @widget(description="no config storage", min_width=200)
    class Bare(IWidget):
        def __init__(self, element):
            self.port = element

        def render(self):
            return None

    # The port carries an override, but this implementation stores no config,
    # so the class declaration stands.
    assert Bare(_StubPort({"min_width": 999})).min_width == 200
