from haywire.barn.builtin.widgets.basic_widgets import (
    CheckboxWidget,
    NumberWidget,
    SelectWidget,
    SimpleLabelWidget,
    SliderWidget,
    SwitchWidget,
    TextWidget,
)


def test_widget_keys_are_builtin_namespaced():
    assert NumberWidget.class_identity.registry_key == "haywire-core:widget:NumberWidget"
    assert SelectWidget.class_identity.registry_key == "haywire-core:widget:SelectWidget"


def test_all_seven_widgets_import():
    assert TextWidget is not None
    assert CheckboxWidget is not None
    assert SwitchWidget is not None
    assert SliderWidget is not None
    assert SimpleLabelWidget is not None


def test_vec_and_color_widgets_exist():
    from haywire.barn.builtin.widgets.color_widget import ColorWidget
    from haywire.barn.builtin.widgets.vec_widget import VecWidget

    assert VecWidget.class_identity.registry_key == "haywire-core:widget:VecWidget"
    assert ColorWidget.class_identity.registry_key == "haywire-core:widget:ColorWidget"
