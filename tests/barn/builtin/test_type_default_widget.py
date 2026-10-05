from haywire.barn.builtin.types import BOOL, COLOR, FLOAT, INT, STRING, VEC3F


def test_each_type_declares_a_default_widget_key():
    assert FLOAT.class_identity.widget_key == "haywire-core:widget:NumberWidget"
    assert INT.class_identity.widget_key == "haywire-core:widget:NumberWidget"
    assert STRING.class_identity.widget_key == "haywire-core:widget:TextWidget"
    assert BOOL.class_identity.widget_key == "haywire-core:widget:SwitchWidget"
    assert COLOR.class_identity.widget_key == "haywire-core:widget:ColorWidget"
    assert VEC3F.class_identity.widget_key == "haywire-core:widget:VecWidget"


def test_vec_type_carries_vec_meta_in_widget_config():
    cfg = VEC3F.class_identity.widget_config
    assert cfg["properties"]["vec_meta"]["length"] == 3
    assert list(cfg["properties"]["vec_meta"]["labels"]) == ["X", "Y", "Z"]


def test_callback_type_has_no_widget_key():
    """CALLBACK declares no widget of its own; it would otherwise inherit STRING's TextWidget."""
    from haywire.barn.builtin.types import CALLBACK

    assert CALLBACK.class_identity.widget_key is None
