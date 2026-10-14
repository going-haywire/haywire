"""A node's props are its only position: no second copy on the wrapper, none in the file."""

from __future__ import annotations

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.graph.types import ChangeReason

pytestmark = pytest.mark.integration


def _key() -> str:
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return TestPrintNode.class_identity.registry_key


def _fresh_graph() -> BaseGraph:
    return BaseGraph(filestem="Fresh", validation_scheduler=SyncScheduler())


def _load(data: dict) -> BaseGraph:
    graph = _fresh_graph()
    graph.load_from_dict(data)
    return graph


def test_serialize_writes_no_position_key(graph_with_library_system):
    wrapper = graph_with_library_system.create_node_wrapper(_key(), position=(40.0, 60.0))
    assert "position" not in wrapper.serialize()


def test_a_node_at_the_origin_round_trips(graph_with_library_system):
    wrapper = graph_with_library_system.create_node_wrapper(_key(), position=(0.0, 0.0))
    data = graph_with_library_system.to_dict()

    restored = _load(data).node_wrappers[wrapper.node_id]

    assert restored.node.props.get_position() == (0.0, 0.0)


def test_a_position_set_through_set_property_survives_save_and_load(
    graph_with_library_system, library_system
):
    graph = graph_with_library_system
    editor = Editor(graph, library_system.get_node_factory())
    wrapper = graph.create_node_wrapper(_key(), position=(10.0, 10.0))

    assert editor.set_property(wrapper.node_id, "posX", 640.0)

    restored = _load(graph.to_dict()).node_wrappers[wrapper.node_id]
    assert restored.node.props.posX == 640.0


def test_a_rebuild_keeps_the_position_only(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper(_key(), position=(10.0, 10.0))
    wrapper.move(640.0, 320.0)
    default_width = wrapper.node.props.width
    wrapper.node.props.width = default_width + 111

    graph.request_node_reset(wrapper.node_id)
    graph._validation.force_immediate_validation()

    assert wrapper.node.props.get_position() == (640.0, 320.0)
    assert wrapper.node.props.width == default_width
    assert "exec" in wrapper.node.ports, "the rebuild ran init()"


def test_a_hot_reload_keeps_the_position(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper(_key(), position=(10.0, 10.0))
    wrapper.move(640.0, 320.0)
    old = wrapper.node

    # What NodeWrapper._on_node_lifecycle_event ends with for a class that does
    # not absorb its own reload.
    graph._validation.mark_node_dirty(wrapper.node_id, ChangeReason.NODE_HOT_RELOADED)
    graph._validation.force_immediate_validation()

    assert wrapper.node is not old, "the node was rebuilt"
    assert wrapper.node.props.get_position() == (640.0, 320.0)


def test_props_win_over_a_stale_file_position(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper(_key(), position=(700.0, 80.0))
    data = graph.to_dict()
    data["nodes"][wrapper.node_id]["position"] = [5, 5]

    restored = _load(data).node_wrappers[wrapper.node_id]

    assert restored.node.props.get_position() == (700.0, 80.0)


def test_a_file_node_without_props_position_loads_at_the_origin(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper(_key(), position=(700.0, 80.0))
    data = graph.to_dict()
    node = data["nodes"][wrapper.node_id]
    # The props bag is serialized twice: under "settings" and at the top of node_data.
    node["node_data"]["settings"].pop("props")
    del node["node_data"]["props"]["values"]["posX"], node["node_data"]["props"]["values"]["posY"]
    node["position"] = [5, 5]
    data["nodes"][wrapper.node_id] = node

    restored = _load(data).node_wrappers[wrapper.node_id]

    assert restored.node.props.get_position() == (0.0, 0.0)


def test_create_node_wrapper_writes_the_given_position_and_runs_init(graph_with_library_system):
    wrapper = graph_with_library_system.create_node_wrapper(_key(), position=(10.0, 20.0))

    assert wrapper.node.props.get_position() == (10.0, 20.0)
    assert "exec" in wrapper.node.ports, "init() ran"


def test_create_node_wrapper_without_a_position_leaves_the_props_default(graph_with_library_system):
    wrapper = graph_with_library_system.create_node_wrapper(_key())

    assert wrapper.node.props.get_position() == (0.0, 0.0)


@pytest.fixture
def construction_fails(monkeypatch):
    """Make ``TestPrintNode`` construction raise for the next ``n`` calls (``arm(n)``)."""
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    original = TestPrintNode.__init__
    state = {"left": 0}

    def flaky(self, *args, **kwargs):
        if state["left"] > 0:
            state["left"] -= 1
            raise RuntimeError("construction failed")
        original(self, *args, **kwargs)

    monkeypatch.setattr(TestPrintNode, "__init__", flaky)

    def arm(n: int = 1) -> None:
        state["left"] = n

    return arm


def _reset(graph, wrapper) -> None:
    graph.request_node_reset(wrapper.node_id)
    graph._validation.force_immediate_validation()


def test_a_rebuild_whose_construction_fails_keeps_the_position(
    graph_with_library_system, construction_fails
):
    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper(_key(), position=(10.0, 10.0))
    wrapper.move(640.0, 320.0)

    construction_fails(1)
    _reset(graph, wrapper)
    assert wrapper._node_instance is None, "the rebuild's construction failed"

    _reset(graph, wrapper)

    assert wrapper.node.props.get_position() == (640.0, 320.0)


def test_a_position_given_to_a_wrapper_without_an_instance_survives_the_first_build(
    graph_with_library_system, construction_fails
):
    from haywire.core.node.node_wrapper import NodeWrapper

    graph = graph_with_library_system
    wrapper = NodeWrapper(registry_key=_key(), node_id="flaky_1", graph=graph)
    construction_fails(1)
    wrapper.build({})
    assert wrapper._node_instance is None

    wrapper.move(10.0, 20.0)
    wrapper.build({})

    assert wrapper.node.props.get_position() == (10.0, 20.0)


def test_the_position_in_node_data_survives_a_failed_first_construction(
    graph_with_library_system, construction_fails
):
    from haywire.core.node.layout import with_position
    from haywire.core.node.node_wrapper import NodeWrapper

    graph = graph_with_library_system
    wrapper = NodeWrapper(registry_key=_key(), node_id="flaky_2", graph=graph)
    construction_fails(1)
    wrapper.build(with_position({}, 700.0, 80.0))
    assert wrapper._node_instance is None

    wrapper.build()

    assert wrapper.node.props.get_position() == (700.0, 80.0)


def test_a_live_instance_ignores_a_stale_pending_position(graph_with_library_system, construction_fails):
    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper(_key(), position=(10.0, 10.0))
    wrapper.move(640.0, 320.0)

    _reset(graph, wrapper)

    assert wrapper._pending_position is None
    assert wrapper.node.props.get_position() == (640.0, 320.0)
