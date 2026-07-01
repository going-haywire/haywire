import haywire.core.graph.editor  # noqa: F401

from haywire.core.settings import NodeSettings, setting
from haywire.barn.builtin.types import FLOAT, INT


def test_choices_desugar_to_select_widget():
    class bag(NodeSettings):
        mode = setting[INT](0, choices={0: "Off", 1: "On"})

    d = bag.__dict__["mode"]
    assert d.resolved_widget_key == "builtin:widget:SelectWidget"
    assert d.resolved_widget_config["properties"]["options"] == {0: "Off", 1: "On"}


def test_min_max_desugar_to_number_config():
    class bag(NodeSettings):
        x = setting[FLOAT](0.5, min=0.0, max=1.0)

    d = bag.__dict__["x"]
    # No explicit widget_key, no choices -> type default (NumberWidget), bounds in config.
    assert d.resolved_widget_key == "builtin:widget:NumberWidget"
    assert d.resolved_widget_config["properties"]["min"] == 0.0
    assert d.resolved_widget_config["properties"]["max"] == 1.0


def test_label_widget_desugars():
    class bag(NodeSettings):
        status = setting[INT](0, widget="label")

    d = bag.__dict__["status"]
    assert d.resolved_widget_key == "builtin:widget:SimpleLabelWidget"
