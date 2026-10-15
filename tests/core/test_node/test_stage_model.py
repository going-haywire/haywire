"""The stage channel, its props fields and on-stage wires."""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.node.layout import CHANNELS, PATCH, STAGE
from haywire.core.node.properties import NodeProperties

from tests.conftest import make_edge, make_node


def test_stage_channel_names_the_stage_fields():
    props = NodeProperties()
    props.set_position((10.0, 20.0), STAGE)
    assert (props.stage_x, props.stage_y) == (10.0, 20.0)
    assert (props.posX, props.posY) == (0.0, 0.0)
    assert CHANNELS == (PATCH, STAGE)
    assert (STAGE.member, STAGE.origin, STAGE.stage) == ("on_stage", 200.0, True)


def test_patch_includes_every_node_and_stage_only_on_stage_nodes():
    props = NodeProperties()
    assert PATCH.includes(props) is True
    assert STAGE.includes(props) is False
    props.on_stage = True
    assert STAGE.includes(props) is True
    assert PATCH.includes(SimpleNamespace()) is True


def test_origin_translation():
    assert STAGE.to_canvas(0, 0) == (200.0, 200.0)
    assert STAGE.from_canvas(200, 260) == (0.0, 60.0)
    assert PATCH.to_canvas(5, 6) == (5.0, 6.0)
    assert PATCH.from_canvas(5, 6) == (5.0, 6.0)


def test_stage_props_defaults():
    props = NodeProperties()
    assert props.on_stage is False
    assert (props.stage_x, props.stage_y) == (0.0, 0.0)
    assert (props.stage_width, props.stage_height) == (200, 200)
    assert props.stage_size_adapt == "auto"


def test_open_view_defaults_to_patch(library_system):
    from haywire.core.graph.properties import GraphProperties

    assert GraphProperties().open_view == "patch"


def _key() -> str:
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return TestPrintNode.class_identity.registry_key


@pytest.mark.integration
def test_stage_fields_round_trip_including_the_origin(graph_with_library_system):
    wrapper = graph_with_library_system.create_node_wrapper(_key(), position=(5.0, 5.0))
    wrapper.node.props.on_stage = True
    wrapper.node.props.set_position((0.0, 0.0), STAGE)

    restored_graph = BaseGraph(filestem="Restored", validation_scheduler=SyncScheduler())
    restored_graph.load_from_dict(graph_with_library_system.to_dict())

    props = restored_graph.node_wrappers[wrapper.node_id].node.props
    assert props.on_stage is True
    assert props.get_position(STAGE) == (0.0, 0.0)


@pytest.mark.integration
def test_a_file_without_stage_fields_loads_off_stage(graph_with_library_system):
    wrapper = graph_with_library_system.create_node_wrapper(_key(), position=(5.0, 5.0))
    data = copy.deepcopy(graph_with_library_system.to_dict())
    for node in data["nodes"].values() if isinstance(data["nodes"], dict) else data["nodes"]:
        values = node["node_data"]["props"]["values"]
        for name in ("on_stage", "stage_x", "stage_y", "stage_width", "stage_height", "stage_size_adapt"):
            values.pop(name, None)

    restored_graph = BaseGraph(filestem="Restored", validation_scheduler=SyncScheduler())
    restored_graph.load_from_dict(data)

    props = restored_graph.node_wrappers[wrapper.node_id].node.props
    assert props.on_stage is False
    assert props.get_position(STAGE) == (0.0, 0.0)


@pytest.mark.integration
def test_annotation_wire_is_on_stage_and_exec_is_not(library_system):
    from haywire.barn.builtin.nodes.annotation import AnnotationNode

    graph = BaseGraph(filestem="Stage Wires", validation_scheduler=SyncScheduler())
    key = AnnotationNode.class_identity.registry_key
    a = make_node(graph, key, position=(0, 0))
    b = make_node(graph, key, position=(400, 0))

    assert a.node.ports["bottom_0"].on_stage is True
    assert a.node.ports["exec"].on_stage is False
    assert a.node.ports["done"].on_stage is False

    edge = make_edge(graph, a.node_id, "bottom_0", b.node_id, "top_0")
    assert edge.on_stage is True
