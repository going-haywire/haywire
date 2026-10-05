"""What @type refuses: a type needs a wire type; a widget is the author's call."""

import pytest

from haywire.core.types.base import PrimitiveType
from haywire.core.types.decorator import type as type_dec

pytestmark = pytest.mark.unit


def test_a_value_type_without_a_wire_type_is_refused():
    with pytest.raises(TypeError, match="needs a wire type"):

        @type_dec(label="NoWire", default={"value": ""})
        class NoWire(PrimitiveType[str]):
            pass


@pytest.mark.parametrize("wire_name", ["ControlWire", "CallbackWire"])
def test_a_signal_type_may_declare_a_widget(wire_name):
    from haywire.barn.builtin import wires

    @type_dec(
        wire_type=getattr(wires, wire_name),
        label="WidgetSignal",
        default={"value": ""},
        widget_key="haywire-core:widget:TextWidget",
    )
    class WidgetSignal(PrimitiveType[str]):
        pass

    assert WidgetSignal.class_identity.widget_key == "haywire-core:widget:TextWidget"


def test_a_signal_type_may_inherit_a_widget():
    from haywire.barn.builtin.types import STRING
    from haywire.barn.builtin.wires import CallbackWire

    @type_dec(wire_type=CallbackWire, label="InheritsWidget")
    class InheritsWidget(STRING):
        pass

    assert InheritsWidget.class_identity.widget_key == STRING.class_identity.widget_key


@pytest.mark.parametrize(
    ("element", "wire_name"),
    [("INT", "DataWire"), ("EXEC", "ControlWire"), ("CALLBACK", "CallbackWire")],
)
def test_optional_travels_on_its_elements_wire_type(element, wire_name):
    from haywire.barn.builtin import types, wires
    from haywire.core.types.wire import wire_type_of

    wire = wire_type_of(types.OPTIONAL[getattr(types, element)])  # type: ignore[misc]

    assert wire is not None
    assert wire.id == getattr(wires, wire_name).id


def test_a_compound_type_needs_no_wire_type():
    from haywire.core.types.base import CompoundType

    @type_dec(label="BareCompound", default={"value": []})
    class BareCompound(CompoundType):
        pass

    assert BareCompound.class_identity.wire_type is None


def test_a_wrapper_type_needs_no_wire_type():
    from haywire.core.types.base import WrapperType

    @type_dec(label="BareWrapper", default={"value": None})
    class BareWrapper(WrapperType):
        pass

    assert BareWrapper.class_identity.wire_type is None


def test_a_bare_any_type_needs_no_wire_type():
    from haywire.core.types.base import BaseType

    @type_dec(label="BareAny", default={"value": None})
    class BareAny(BaseType):
        _is_any = True

    assert BareAny.class_identity.wire_type is None
