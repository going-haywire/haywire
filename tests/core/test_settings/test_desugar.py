from haywire.core.settings import NodeSettings, setting
from haywire.barn.builtin.types import CHOICES, FLOAT, INT
from haywire.barn.builtin.widgets.basic_widgets import SimpleLabelWidget


def test_choices_type_stamps_select_widget():
    class bag(NodeSettings):
        mode = setting[CHOICES](0, widget_config={"options": {0: "Off", 1: "On"}})

    d = bag.__dict__["mode"]
    assert d.widget_key == "haywire-core:widget:SelectWidget"
    assert d.widget_config["properties"]["options"] == {0: "Off", 1: "On"}


def test_min_max_desugar_to_number_config():
    class bag(NodeSettings):
        x = setting[FLOAT](0.5, min=0.0, max=1.0)

    d = bag.__dict__["x"]
    # No explicit widget=, no widget_config override -> type default (NumberWidget), bounds in config.
    assert d.widget_key == "haywire-core:widget:NumberWidget"
    assert d.widget_config["properties"]["min"] == 0.0
    assert d.widget_config["properties"]["max"] == 1.0


def test_label_widget_stamped_via_explicit_widget_dict():
    class bag(NodeSettings):
        status = setting[INT](0, widget=SimpleLabelWidget.config())

    d = bag.__dict__["status"]
    assert d.widget_key == "haywire-core:widget:SimpleLabelWidget"
