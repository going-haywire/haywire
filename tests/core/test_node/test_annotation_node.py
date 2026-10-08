"""The annotation node: a box of text whose card sides each grow a set of swinglets for styled arrows."""

from typing import Any

import pytest

from haywire.core.execution.event_source import SystemEventType
from haywire.core.execution.interpreter import Interpreter
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.types import PortOrigin

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration


@pytest.fixture
def graph(library_system) -> BaseGraph:
    return BaseGraph(filestem="Annotation Graph", validation_scheduler=SyncScheduler())


def _key() -> str:
    from haywire.barn.builtin.nodes.annotation import AnnotationNode

    return AnnotationNode.class_identity.registry_key


def _notes(graph: BaseGraph):
    a = make_node(graph, _key(), position=(0, 0))
    b = make_node(graph, _key(), position=(400, 0))
    return a, b


def test_a_new_node_has_four_swinglet_slots_and_a_control_pair(graph):
    from haywire.barn.builtin.nodes.annotation import AnnotationNode
    from haywire.barn.builtin.types import ADD, ANNOTATION, EXEC

    a = make_node(graph, _key())
    assert isinstance(a.node, AnnotationNode)
    ports = a.node.ports
    for side in AnnotationNode.SIDES:
        slot = ports[f"{side}_0"]
        assert slot.type_cls is ADD[ANNOTATION]
        assert slot.is_swinglet()
        assert slot.label == f"{side.title()} 0"
    assert ports["exec"].type_cls is EXEC
    assert ports["exec"].is_inlet()
    assert ports["done"].type_cls is EXEC
    assert ports["done"].is_outlet()
    assert len(ports) == 6


def test_linking_two_notes_grows_a_pin_on_each_side_used(graph):
    from haywire.barn.builtin.types import ADD, ANNOTATION
    from haywire.barn.builtin.types.annotation import AnnotationStyle

    a, b = _notes(graph)
    edge = make_edge(graph, a.node_id, "bottom_0", b.node_id, "top_0")
    graph.force_validation()

    for wrapper, side in ((a, "bottom"), (b, "top")):
        grown = wrapper.node.ports[f"{side}_0"]
        assert grown.type_cls is ANNOTATION
        assert grown.origin is PortOrigin.RESOLVED
        assert grown.is_swinglet()
        assert wrapper.node.ports[f"{side}_1"].type_cls is ADD[ANNOTATION]
        assert wrapper.node.ports[f"{side}_1"].is_swinglet()

    assert edge.is_valid()
    assert isinstance(edge.style, AnnotationStyle)
    assert edge.propagation is None
    assert not edge.carries_values


def test_a_port_id_records_its_side():
    from haywire.barn.builtin.nodes.annotation import AnnotationNode

    assert AnnotationNode.side_of("left_3") == "left"
    assert AnnotationNode.side_of("top_0") == "top"
    assert AnnotationNode.side_of("exec") is None
    assert AnnotationNode.side_of("root_in") is None
    assert AnnotationNode.side_of("left_in_0") is None


def test_each_side_grows_on_its_own(graph):
    from haywire.barn.builtin.types import ADD, ANNOTATION

    a, b = _notes(graph)
    make_edge(graph, a.node_id, "right_0", b.node_id, "left_0")
    graph.force_validation()
    make_edge(graph, a.node_id, "right_1", b.node_id, "top_0")
    graph.force_validation()

    assert a.node.ports["right_0"].type_cls is ANNOTATION
    assert a.node.ports["right_1"].type_cls is ANNOTATION
    assert a.node.ports["right_2"].type_cls is ADD[ANNOTATION]
    for side in ("top", "bottom", "left"):
        assert a.node.ports[f"{side}_0"].type_cls is ADD[ANNOTATION]
        assert f"{side}_1" not in a.node.ports


def test_indices_are_never_reused(graph):
    from haywire.core.node.promotion import remove_port

    a, b = _notes(graph)
    make_edge(graph, a.node_id, "right_0", b.node_id, "left_0")
    graph.force_validation()
    assert remove_port(b.node, "left_0")
    graph.force_validation()

    make_edge(graph, a.node_id, "right_1", b.node_id, "left_1")
    graph.force_validation()
    assert "left_2" in b.node.ports
    assert "left_0" not in b.node.ports


def test_removing_a_grown_pin_leaves_its_edge_on_the_ghost(graph):
    from haywire.core.node.promotion import remove_port

    a, b = _notes(graph)
    edge = make_edge(graph, a.node_id, "bottom_0", b.node_id, "top_0")
    graph.force_validation()

    assert remove_port(b.node, "top_0")
    graph.force_validation()

    assert edge.edge_id in graph.edge_wrappers
    assert not edge.is_valid()
    assert "top_1" in b.node.ports


def test_slots_are_not_removable_and_grown_pins_are(graph):
    a, b = _notes(graph)
    make_edge(graph, a.node_id, "right_0", b.node_id, "left_0")
    graph.force_validation()

    assert b.node.ports["left_0"].is_user_removable()
    assert not b.node.ports["left_1"].is_user_removable()
    assert not b.node.ports["exec"].is_user_removable()


def test_an_unlinked_note_is_valid(graph):
    a = make_node(graph, _key())
    graph.force_validation()
    assert a.is_valid()


def test_the_worker_passes_control_and_its_payload_through(graph):
    a = make_node(graph, _key())
    a.node.ports["exec"].set_value({"k": 1})
    assert a.node.worker(None) == "done"  # type: ignore[arg-type]
    assert a.node.ports["done"].get_value() == {"k": 1}


@pytest.mark.slow
def test_a_note_in_a_control_chain_forwards_the_payload(graph_with_library_system: BaseGraph):
    from haybale_testing.nodes.testbed.begin_play_node import TestBeginPlayNode
    from haybale_testing.nodes.testbed.control_payload_node import ControlPayloadTestNode

    graph = graph_with_library_system
    begin = make_node(graph, TestBeginPlayNode.class_identity.registry_key, position=(0, 0))
    emitter = make_node(graph, ControlPayloadTestNode.class_identity.registry_key, position=(200, 0))
    note = make_node(graph, _key(), position=(400, 0))
    sink = make_node(graph, ControlPayloadTestNode.class_identity.registry_key, position=(600, 0))
    assert isinstance(emitter.node, ControlPayloadTestNode)
    assert isinstance(sink.node, ControlPayloadTestNode)
    emitter.node.emit_payload = {"k": 1}  # type: ignore[assignment]

    make_edge(graph, begin.node_id, "exec", emitter.node_id, "exec_in")
    make_edge(graph, emitter.node_id, "exec_out", note.node_id, "exec")
    make_edge(graph, note.node_id, "done", sink.node_id, "exec_in")

    interpreter = Interpreter()
    interpreter.load_graph(graph)
    try:
        interpreter.dispatch_system_event(SystemEventType.BEGIN_PLAY)
        interpreter.wait_all(timeout=5.0)
    finally:
        interpreter.shutdown()

    assert sink.node.received == {"k": 1}


def test_a_note_round_trips_with_its_pins_text_and_edge_style(graph):
    from haywire.barn.builtin.types import ANNOTATION
    from haywire.barn.builtin.types.annotation import AnnotationStyle

    a, b = _notes(graph)
    props: Any = a.node.props
    props.text = "line 1\nline 2"
    edge = make_edge(graph, a.node_id, "right_0", b.node_id, "left_0")
    graph.force_validation()
    assert isinstance(edge.style, AnnotationStyle)
    edge.style.color = "#ff0000"

    data = graph.to_dict()
    loaded = BaseGraph(filestem="Loaded", validation_scheduler=SyncScheduler())
    assert loaded.load_from_dict(data)
    loaded.force_validation()

    la = loaded.node_wrappers[a.node_id]
    lb = loaded.node_wrappers[b.node_id]
    loaded_props: Any = la.node.props
    assert loaded_props.text == "line 1\nline 2"
    assert la.node.ports["right_0"].type_cls is ANNOTATION
    assert la.node.ports["right_0"].is_swinglet()
    assert "right_1" in la.node.ports
    assert lb.node.ports["left_0"].type_cls is ANNOTATION
    assert "left_2" not in lb.node.ports
    (reloaded,) = loaded.edge_wrappers.values()
    assert reloaded.is_valid()
    assert isinstance(reloaded.style, AnnotationStyle)
    assert reloaded.style.color == "#ff0000"


def test_the_skin_is_bound_by_key_and_text_redraws(graph):
    a = make_node(graph, _key())
    assert a.node.props.skin == "haywire-core:skin:AnnotationSkin"
    fields = type(a.node.props).REDRAW_FIELDS
    assert "text" in fields
    assert "show_control_pins" in fields
    assert "skin" in fields
    props: Any = a.node.props
    assert props.show_control_pins is False
