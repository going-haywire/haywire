# tests/ui/widget/test_optional_widget.py
"""
OptionalWidget — renders an ``OPTIONAL[T]`` field in two states.

The delegation is the whole design: this widget never names an element type. It
reads the element off the cell, looks up THAT type's declared widget key, and
builds it. So the tests that matter are the ones proving it works for element
types it was never written against — a number, a switch, a select, and a vector
whose widget cannot render without ``vec_meta`` inherited through the wrapper's
identity.

Real NiceGUI elements need a Client slot context, hence the integration marker
(same pattern as test_set_enabled.py).
"""

from typing import Any, cast

import pytest
from nicegui import Client

from haywire.barn.builtin import widgets as builtin_widgets
from haywire.barn.builtin.types import BOOL, CHOICES, FLOAT, INT, VEC3F, OPTIONAL
from haywire.barn.builtin.widgets.optional_widget import OptionalWidget
from haywire.ui.panel.setting_widget_model import SettingWidgetModel
from haywire.ui.widget.globals import WIDGET_REGISTRY

pytestmark = pytest.mark.integration


def _noop_page() -> None:  # registration target for a headless Client
    pass


@pytest.fixture(autouse=True)
def registered_builtin_widgets():
    """Populate the global widget registry the way a library load would.

    ``@widget`` only stamps an identity; ``WidgetRegistry`` is what publishes a
    class into ``WIDGET_REGISTRY``, and no library is loaded here. Restores the
    previous contents so the registry can't leak between tests.
    """
    before = dict(WIDGET_REGISTRY)
    for name in builtin_widgets.__all__:
        cls = getattr(builtin_widgets, name)
        WIDGET_REGISTRY[cls.class_identity.registry_key] = cls
    yield
    WIDGET_REGISTRY.clear()
    WIDGET_REGISTRY.update(before)


def _rendered(element_cls, initial=None, widget_config=None):
    """An OptionalWidget bound to a real OPTIONAL[element] cell.

    Returns ``(widget, cell, edits)``. ``on_edit`` collects writes rather than
    applying them — the panel's write policy is not under test here, only what
    the widget asks for.
    """
    edits: list = []
    # Bridge through Any: element_cls is a runtime value, so mypy reads the
    # subscript as a type expression (same reason registry.resolve_type_from_spec
    # does this).
    wrapper: Any = OPTIONAL
    cell = wrapper[element_cls].create_field(default_override={"value": initial})
    model = SettingWidgetModel(
        field_id="opt",
        widget_config=widget_config or {"properties": {}},
        cell=cell,
        on_edit=edits.append,
    )
    widget = OptionalWidget(model)
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        widget.render()
    return widget, cell, edits


class TestDelegation:
    @pytest.mark.parametrize(
        ("element_cls", "expected_inner"),
        [
            (INT, "NumberWidget"),
            (FLOAT, "NumberWidget"),
            (BOOL, "SwitchWidget"),
            (CHOICES, "SelectWidget"),
            (VEC3F, "VecWidget"),
        ],
    )
    def test_builds_the_element_types_own_widget(self, element_cls, expected_inner):
        widget, _, _ = _rendered(element_cls, initial=None)
        assert type(cast(Any, widget)._inner).__name__ == expected_inner

    def test_vector_element_receives_the_vec_meta_it_cannot_render_without(self):
        # VEC3F declares vec_meta on its IDENTITY, not per-declaration. It reaches
        # the inner widget only because the wrapper's parameterized identity
        # merges the element's widget properties in (_wrapped_identity).
        props = OPTIONAL[VEC3F].class_identity.widget_config["properties"]
        assert props["vec_meta"]["length"] == 3

    def test_unknown_element_widget_falls_back_to_a_label(self):
        # A missing widget must never render a silent blank cell — same rule the
        # panel applies for an unknown widget_key.
        del WIDGET_REGISTRY[builtin_widgets.NumberWidget.class_identity.registry_key]
        widget, _, _ = _rendered(INT, initial=3)
        assert cast(Any, widget)._inner is None
        assert cast(Any, widget)._inner_label.text == "3"


class TestAbsenceState:
    def test_absent_hides_the_element_widget(self):
        # A cleared cell holds None, which PrimitiveUnwrappingConverter renders
        # as 0 — a number that lies about the value. So the element widget is
        # hidden rather than shown holding a stand-in.
        widget, _, _ = _rendered(INT, initial=None)
        assert cast(Any, widget)._none_cell.visible
        assert not cast(Any, widget)._value_cell.visible

    def test_present_hides_the_none_affordance(self):
        widget, _, _ = _rendered(INT, initial=5)
        assert not cast(Any, widget)._none_cell.visible
        assert cast(Any, widget)._value_cell.visible

    def test_state_follows_the_cell(self):
        widget, cell, _ = _rendered(INT, initial=5)
        cell.set_value(None)
        assert cast(Any, widget)._none_cell.visible
        cell.set_value(7)
        assert not cast(Any, widget)._none_cell.visible

    def test_the_absence_cell_is_framed_like_a_value_widget(self):
        # Same height and framing as NumberDrag's own rule, so the value column
        # doesn't jump when a field is cleared.
        widget, _, _ = _rendered(INT, initial=None)
        assert "hw-optional-none" in cast(Any, widget)._none_cell._classes

    def test_the_absence_cell_carries_a_visible_action_icon(self):
        # It must read as a control, not as inert text. Hover-revealing the
        # icon would hide the only signal that the cell does anything.
        widget, _, _ = _rendered(INT, initial=None)
        children = cast(Any, widget)._none_cell.default_slot.children
        assert any("hw-optional-none__action" in c._classes for c in children)


class TestRestore:
    def test_the_widget_offers_no_clear_of_its_own(self):
        # Leaving absence is the widget's job; entering it is the row menu's.
        # A clear button here would duplicate "Reset to default" (for a field
        # defaulting to absence) or "Set to none" (for one defaulting to a
        # value) — a third control the user must distinguish for no benefit.
        widget, _, _ = _rendered(INT, initial=5)
        assert not hasattr(widget, "_clear_button")

    def test_restore_uses_the_element_default_when_nothing_is_declared(self):
        widget, _, edits = _rendered(INT, initial=None)
        cast(Any, widget)._on_restore()
        assert edits == [cast(dict, INT.class_identity.default)["value"]]

    def test_restore_prefers_a_declared_restore_value(self):
        # The per-use knob (widget_config={"restore": ...}); the field's own
        # non-absent default arrives through the same channel, stamped by
        # setting._stamp_widget.
        widget, _, edits = _rendered(INT, initial=None, widget_config={"properties": {"restore": 42}})
        cast(Any, widget)._on_restore()
        assert edits == [42]

    def test_restore_is_stateless(self):
        # Deliberately NOT "the last value you had". A remembered value dies on
        # every panel redraw, so the same gesture would give different answers
        # depending on invisible state — the path-dependence this whole design
        # exists to eliminate.
        widget, cell, edits = _rendered(INT, initial=None, widget_config={"properties": {"restore": 42}})
        cell.set_value(9)
        cell.set_value(None)
        cast(Any, widget)._on_restore()
        assert edits == [42]


class TestInnerModel:
    def test_inner_widget_shares_the_outer_cell(self):
        # Not a copy: the inner widget's own on_changed subscription and any
        # binding it registers must stay live against the real cell.
        widget, cell, _ = _rendered(INT, initial=5)
        assert cast(Any, widget)._inner.port.data is cell

    def test_inner_widget_never_sees_none(self):
        widget, _, _ = _rendered(INT, initial=None, widget_config={"properties": {"restore": 42}})
        assert cast(Any, widget)._inner.port.get_value() == 42

    def test_inner_widget_writes_forward_to_the_outer_model(self):
        widget, _, edits = _rendered(INT, initial=5)
        cast(Any, widget)._inner.port.set_value(8)
        assert edits == [8]


class TestCleanup:
    def test_cleanup_releases_the_inner_widget(self):
        widget, _, _ = _rendered(INT, initial=5)
        inner = cast(Any, widget)._inner
        widget.cleanup()
        assert cast(Any, inner)._cleaned_up
        assert cast(Any, widget)._inner is None
