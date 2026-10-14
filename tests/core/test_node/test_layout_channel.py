"""LayoutChannel: which props fields a canvas lays a node out with."""

import copy

import pytest

from haywire.core.node.layout import PATCH, LayoutChannel, position_of, with_position
from haywire.core.node.properties import NodeProperties

SWAPPED = LayoutChannel(
    "swapped", x="posY", y="posX", width="height", height="width", size_adapt="size_adapt"
)


def _node(values: dict | None = None) -> dict:
    return {
        "node_id": "n1",
        "node_data": {"props": {"values": dict(values or {}), "other": 1}, "store": {"k": "v"}},
    }


def test_patch_names_the_pos_fields():
    assert (PATCH.name, PATCH.x, PATCH.y) == ("patch", "posX", "posY")


def test_position_of_reads_props_values():
    assert position_of(_node({"posX": 12.5, "posY": 3})) == (12.5, 3.0)


def test_position_of_reads_a_missing_field_as_zero():
    assert position_of(_node({"posY": 7.0})) == (0.0, 7.0)
    assert position_of({"node_id": "n1"}) == (0.0, 0.0)
    assert position_of({"node_data": {}}) == (0.0, 0.0)
    assert position_of({"node_data": {"props": {}}}) == (0.0, 0.0)


def test_with_position_copies():
    original = _node({"width": 300})
    snapshot = copy.deepcopy(original["node_data"])
    result = with_position(original["node_data"], 1.0, 2.0)
    assert original["node_data"] == snapshot
    assert result["props"]["values"] == {"width": 300, "posX": 1.0, "posY": 2.0}
    assert result["props"]["other"] == 1
    assert result["store"] == {"k": "v"}


def test_with_position_accepts_none():
    assert with_position(None, 1.0, 2.0) == {"props": {"values": {"posX": 1.0, "posY": 2.0}}}


def test_a_channel_names_the_fields():
    props = NodeProperties()
    props.set_position((1.0, 2.0), SWAPPED)
    assert props.posY == 1.0
    assert props.posX == 2.0
    assert props.get_position(SWAPPED) == (1.0, 2.0)
    assert props.get_position() == (2.0, 1.0)


@pytest.mark.integration
@pytest.mark.parametrize("pos", [(0.0, 0.0), (120.5, 40.0)])
def test_position_of_matches_a_real_serialization(graph_with_library_system, pos):
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    wrapper = graph_with_library_system.create_node_wrapper(
        TestPrintNode.class_identity.registry_key, position=(5, 5)
    )
    wrapper.node.props.set_position(pos)
    assert position_of(wrapper.serialize()) == pos
