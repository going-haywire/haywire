from haywire.barn.builtin.types import CHOICES, FLOAT
from haywire.barn.builtin import widget_keys
from haywire.core.settings import Settings, setting


class Bag(Settings):
    plain = setting[FLOAT](0.5, min=0.0, max=1.0)
    picked = setting[CHOICES]("fast", widget_config={"options": ["fast", "precise"]})


def test_widget_key_stamped_from_itype():
    d = Bag.__dict__["plain"]
    assert d.widget_key == widget_keys.NUMBER_WIDGET
    assert d.widget_config["properties"]["min"] == 0.0
    assert d.widget_config["properties"]["max"] == 1.0


def test_choices_type_carries_select_and_options():
    d = Bag.__dict__["picked"]
    assert d.widget_key == widget_keys.SELECT_WIDGET
    assert d.widget_config["properties"]["options"] == ["fast", "precise"]


def test_explicit_widget_dict_wins():
    class Bag2(Settings):
        f = setting[FLOAT](0.5, widget={"key": widget_keys.TEXT_WIDGET, "config": {"properties": {}}})

    assert Bag2.__dict__["f"].widget_key == widget_keys.TEXT_WIDGET


def test_choices_kwarg_is_gone():
    import pytest

    with pytest.raises(TypeError):
        setting[CHOICES]("fast", choices=["fast"])  # deleted kwarg
