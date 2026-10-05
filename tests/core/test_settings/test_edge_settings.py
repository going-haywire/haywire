"""A style bag is a settings flavour of its own, named by a wire type."""

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.settings import EdgeSettings, setting
from haywire.core.types.wire import WireRole, WireType

pytestmark = pytest.mark.unit


class _Style(EdgeSettings):
    width = setting[FLOAT](3.0, label="Width")


def test_an_edge_bag_has_no_node_and_keeps_its_edge():
    edge = object()
    bag = _Style(edge=edge)  # type: ignore[arg-type]
    assert bag._node is None
    assert bag._edge is edge


def test_an_edge_bag_round_trips_its_set_values():
    bag = _Style()
    bag.width = 5.0
    restored = _Style()
    restored._from_dict({"values": bag._to_dict()["values"]})
    assert restored.width == 5.0
    assert restored._is_locally_set("width")


def test_an_unknown_key_is_skipped():
    bag = _Style()
    bag._from_dict({"values": {"colour": "#ff0000", "width": 4.0}})
    assert bag._to_dict()["values"] == {"width": 4.0}


def test_a_wire_type_has_no_style_by_default():
    class _Plain(WireType):
        role = WireRole.VISUAL

    assert _Plain.style is None


def test_a_wire_type_names_its_style_bag():
    class _Styled(WireType):
        role = WireRole.VISUAL
        style = _Style

    assert _Styled.style is _Style


def test_a_style_that_is_no_edge_bag_is_refused():
    with pytest.raises(TypeError, match="EdgeSettings"):

        class _Wrong(WireType):
            role = WireRole.VISUAL
            style = dict  # type: ignore[assignment]


def test_the_test_visual_wire_declares_every_recognised_field():
    from haybale_testing.wires import TestVisualStyle, TestVisualWire

    from haywire.core.edge.style import STYLE_FIELDS
    from haywire.core.settings import settings_fields

    assert TestVisualWire.style is TestVisualStyle
    assert tuple(settings_fields(TestVisualStyle)) == STYLE_FIELDS
