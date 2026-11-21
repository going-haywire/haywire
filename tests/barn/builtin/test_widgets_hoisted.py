from haywire.barn.builtin.widgets.basic_widgets import (
    CheckboxWidget,
    NumberWidget,
    MenuWidget,
    LabelWidget,
    SliderWidget,
    ToggleWidget,
    TextWidget,
)


def test_widget_keys_are_builtin_namespaced():
    assert NumberWidget.class_identity.registry_key == "haywire-core:widget:NumberWidget"
    assert MenuWidget.class_identity.registry_key == "haywire-core:widget:MenuWidget"


def test_all_seven_widgets_import():
    assert TextWidget is not None
    assert CheckboxWidget is not None
    assert ToggleWidget is not None
    assert SliderWidget is not None
    assert LabelWidget is not None


def test_vec_and_color_widgets_exist():
    from haywire.barn.builtin.widgets.color_widget import ColorWidget
    from haywire.barn.builtin.widgets.vector_widget import VectorWidget

    assert VectorWidget.class_identity.registry_key == "haywire-core:widget:VectorWidget"
    assert ColorWidget.class_identity.registry_key == "haywire-core:widget:ColorWidget"
