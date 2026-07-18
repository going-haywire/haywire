import pytest

from haywire.barn.builtin.types import BOOL, COLOR, FLOAT, INT, STRING, VEC3F


def test_each_type_declares_a_default_widget_key():
    assert FLOAT.class_identity.widget_key == "builtin:widget:NumberWidget"
    assert INT.class_identity.widget_key == "builtin:widget:NumberWidget"
    assert STRING.class_identity.widget_key == "builtin:widget:TextWidget"
    assert BOOL.class_identity.widget_key == "builtin:widget:SwitchWidget"
    assert COLOR.class_identity.widget_key == "builtin:widget:ColorWidget"
    assert VEC3F.class_identity.widget_key == "builtin:widget:VecWidget"


def test_vec_type_carries_vec_meta_in_widget_config():
    cfg = VEC3F.class_identity.widget_config
    assert cfg["properties"]["vec_meta"]["length"] == 3
    assert list(cfg["properties"]["vec_meta"]["labels"]) == ["X", "Y", "Z"]


def test_callback_type_has_no_widget_key():
    """CALLBACK inherits STRING's payload but must NOT inherit its TextWidget."""
    from haybale_core.types.specs import CALLBACK

    assert CALLBACK.class_identity.widget_key is None


@pytest.mark.parametrize("flow", ["control", "callback"])
def test_control_and_callback_flow_types_reject_widget_key(flow):
    """A signal pin (CONTROL/CALLBACK) with a widget_key is rejected at decoration."""
    from haywire.core.types.base import PrimitiveType
    from haywire.core.types.decorator import type as type_dec
    from haywire.core.types.enums import FlowType

    flow_type = FlowType.CONTROL if flow == "control" else FlowType.CALLBACK

    with pytest.raises(TypeError, match="cannot have a widget_key"):

        @type_dec(
            flow_type=flow_type,
            label="BadSignal",
            default={"value": ""},
            widget_key="builtin:widget:TextWidget",
        )
        class BadSignal(PrimitiveType[str]):
            pass


def test_inherited_widget_key_on_signal_type_is_rejected():
    """The inheritance trap: a CALLBACK derived from a widgeted scalar must clear it."""
    from haywire.core.types.decorator import type as type_dec
    from haywire.core.types.enums import FlowType

    with pytest.raises(TypeError, match="inherits a widget_key|cannot have a widget_key"):

        @type_dec(flow_type=FlowType.CALLBACK, label="BadCb", default={}, color="#fff")
        class BadInheritedCallback(STRING):  # inherits STRING's TextWidget, no override
            pass
