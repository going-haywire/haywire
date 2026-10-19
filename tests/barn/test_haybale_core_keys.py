"""The registry keys haybale-core names by string match the classes they name."""

import pytest

pytestmark = pytest.mark.integration


def test_haybale_core_keys_match_their_classes():
    from haybale_core.keys import ARRAY_WIDGET, WIDGET_NODE_SKIN
    from haybale_core.skins.widget_node_skin import WidgetNodeSkin
    from haybale_core.widgets.array_widget import ArrayWidget

    assert ARRAY_WIDGET == ArrayWidget.class_identity.registry_key
    assert WIDGET_NODE_SKIN == WidgetNodeSkin.class_identity.registry_key


def test_the_slider_widget_key_matches_its_class():
    from haywire.barn.builtin.widget_keys import SLIDER_WIDGET
    from haywire.barn.builtin.widgets import SliderWidget

    assert SLIDER_WIDGET == SliderWidget.class_identity.registry_key
