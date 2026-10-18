"""The graph measures one canvas extent per channel and moves nodes on and off the stage."""

from __future__ import annotations

import pytest

from haywire.core.graph.base import _CANVAS_MIN_SIZE
from haywire.core.graph.editor import Editor
from haywire.core.graph.stage import STAGE_MARGIN, next_stage_spot
from haywire.core.graph.types import ChangeReason, ValidationResult
from haywire.core.node.layout import PATCH, STAGE

pytestmark = pytest.mark.integration


def _key() -> str:
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return TestPrintNode.class_identity.registry_key


def _editor(graph, library_system) -> Editor:
    return Editor(graph, library_system.get_node_factory())


def _collect(graph) -> list[ValidationResult]:
    """Return the list the graph's validation batches are appended to.

    The fixture graph validates synchronously, so every write is its own batch.
    """
    results: list[ValidationResult] = []
    graph._validation.subscribe(results.append)
    return results


def _node(graph, x: float = 0.0, y: float = 0.0):
    return graph.create_node_wrapper(_key(), position=(x, y))


# ---------------------------------------------------------------------------
# Extents
# ---------------------------------------------------------------------------


def test_stage_extent_measures_only_on_stage_nodes_plus_the_origin(graph_with_library_system):
    graph = graph_with_library_system
    off = _node(graph)
    on = _node(graph)
    off.node.props.stage_x = 9000.0
    off.node.props.stage_y = 9000.0
    on.node.props.on_stage = True
    on.node.props.stage_x = 4500.0

    graph._check_canvas_size(STAGE)

    width, height = graph.canvas_extent(STAGE)
    assert width > 4500 + STAGE.origin  # the on-stage node grows the width
    assert width < 9000  # the off-stage node at 9000 does not
    assert height == _CANVAS_MIN_SIZE


def test_stage_extent_of_an_empty_stage_is_the_minimum(graph_with_library_system):
    graph = graph_with_library_system
    node = _node(graph)
    node.node.props.stage_x = 9000.0

    graph._check_canvas_size(STAGE)

    assert graph.canvas_extent(STAGE) == (_CANVAS_MIN_SIZE, _CANVAS_MIN_SIZE)


def test_patch_extent_is_unchanged_by_stage_moves(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = _node(graph)
    before = (graph.canvas_width, graph.canvas_height)

    assert graph.move_node(wrapper.node_id, 9000, 9000, STAGE)

    assert (graph.canvas_width, graph.canvas_height) == before
    assert graph.canvas_extent(PATCH) == before


def test_validation_result_carries_extents_per_channel(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = _node(graph)
    results = _collect(graph)

    graph.move_node(wrapper.node_id, 9500, 100, PATCH)
    patch_sizes = [r.canvas_sizes for r in results if r.canvas_sizes]
    assert patch_sizes == [{"patch": graph.canvas_extent(PATCH)}]
    assert patch_sizes[0]["patch"][0] > _CANVAS_MIN_SIZE

    results.clear()
    wrapper.node.props.on_stage = True
    graph.move_node(wrapper.node_id, 8000, 100, STAGE)
    stage_sizes = [r.canvas_sizes for r in results if r.canvas_sizes]
    assert stage_sizes
    assert all(set(sizes) == {"stage"} for sizes in stage_sizes)  # the patch extent did not change
    assert stage_sizes[-1]["stage"] == graph.canvas_extent(STAGE)
    assert stage_sizes[-1]["stage"][0] > 8000


def test_add_and_remove_check_every_channel(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = _node(graph)
    wrapper.node.props.on_stage = True
    wrapper.node.props.stage_x = 6000.0
    graph._check_canvas_size(STAGE)
    assert graph.canvas_extent(STAGE)[0] > _CANVAS_MIN_SIZE

    graph.remove_node_wrapper(wrapper)

    assert graph.canvas_extent(STAGE) == (_CANVAS_MIN_SIZE, _CANVAS_MIN_SIZE)


# ---------------------------------------------------------------------------
# NODE_STAGE_CHANGED
# ---------------------------------------------------------------------------


def test_stage_changed_reason_is_save_relevant_and_ranks_with_redraw():
    reason = ChangeReason.NODE_STAGE_CHANGED
    assert not reason.requires_redraw()
    assert not reason.is_visual_only()
    assert not reason.requires_graph_reassembly()
    assert reason.get_priority() == ChangeReason.NODE_REDRAW_REQUESTED.get_priority()
    assert ValidationResult(nodes={"n": reason}).requires_save()
    assert not ValidationResult(nodes={"n": reason}).requires_reassembly()


def test_on_stage_write_raises_node_stage_changed(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    a = _node(graph)
    b = _node(graph)
    results = _collect(graph)

    assert editor.set_property(a.node_id, "on_stage", True)
    assert any(r.nodes.get(a.node_id) is ChangeReason.NODE_STAGE_CHANGED for r in results)
    assert any(r.requires_save() for r in results)
    assert not any(r.requires_reassembly() for r in results)

    results.clear()
    b.node.props.on_stage = True
    assert [r.nodes.get(b.node_id) for r in results] == [ChangeReason.NODE_STAGE_CHANGED]
    assert results[0].requires_save()
    assert not results[0].requires_reassembly()
    assert results[0].graph is None


# ---------------------------------------------------------------------------
# next_stage_spot
# ---------------------------------------------------------------------------


def test_next_stage_spot_on_an_empty_stage(graph_with_library_system):
    graph = graph_with_library_system
    assert next_stage_spot(graph, 1) == [(STAGE_MARGIN, STAGE_MARGIN)]


def test_next_stage_spot_stacks_by_height(graph_with_library_system):
    graph = graph_with_library_system
    spots = next_stage_spot(graph, 3, heights=[100, 50, 70])
    assert spots == [(40.0, 40.0), (40.0, 180.0), (40.0, 270.0)]


# ---------------------------------------------------------------------------
# Add / Remove from Stage
# ---------------------------------------------------------------------------


def test_add_to_stage_places_by_the_margin_rule(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    first = _node(graph, 0, 0)
    second = _node(graph, 0, 100)
    third = _node(graph, 0, 200)

    assert editor.add_to_stage([first.node_id])
    assert first.node.props.on_stage is True
    assert (first.node.props.stage_x, first.node.props.stage_y) == (40.0, 40.0)
    assert first.node.props.stage_size_adapt == "auto"

    assert editor.add_to_stage([second.node_id])
    expected_y = first.node.props.stage_y + first.node.props.stage_height + STAGE_MARGIN
    assert (second.node.props.stage_x, second.node.props.stage_y) == (40.0, expected_y)

    # Several at once stack in patch order, whatever order the ids arrive in.
    fourth = _node(graph, 0, 50)
    assert editor.add_to_stage([third.node_id, fourth.node_id])
    assert fourth.node.props.stage_y < third.node.props.stage_y
    assert fourth.node.props.stage_y == second.node.props.stage_y + second.node.props.stage_height + 40.0


def test_add_to_stage_skips_nodes_already_there(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    wrapper = _node(graph)
    assert editor.add_to_stage([wrapper.node_id])

    assert editor.add_to_stage([wrapper.node_id]) is False
    assert editor.add_to_stage(["missing"]) is False
    assert editor.remove_from_stage([]) is False

    # The refused calls recorded nothing: one undo reverts the only add.
    assert editor.history_manager.undo()
    assert wrapper.node.props.on_stage is False


def test_add_and_remove_are_one_undo_step_each(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    wrapper = _node(graph)
    props = wrapper.node.props
    props.stage_x = 7.0
    props.stage_y = 9.0
    props.stage_size_adapt = "manual"

    assert editor.add_to_stage([wrapper.node_id])
    assert (props.on_stage, props.stage_x, props.stage_y) == (True, 40.0, 40.0)
    assert props.stage_size_adapt == "auto"

    assert editor.history_manager.undo()
    assert props.on_stage is False
    assert (props.stage_x, props.stage_y, props.stage_size_adapt) == (7.0, 9.0, "manual")

    assert editor.history_manager.redo()
    assert (props.on_stage, props.stage_x, props.stage_y, props.stage_size_adapt) == (
        True,
        40.0,
        40.0,
        "auto",
    )

    assert editor.remove_from_stage([wrapper.node_id])
    assert props.on_stage is False
    assert editor.history_manager.undo()
    assert props.on_stage is True
    assert editor.history_manager.redo()
    assert props.on_stage is False


def test_remove_from_stage_keeps_the_stage_rect(graph_with_library_system, library_system):
    graph = graph_with_library_system
    editor = _editor(graph, library_system)
    wrapper = _node(graph)
    editor.add_to_stage([wrapper.node_id])
    props = wrapper.node.props
    props.stage_width = 321
    props.stage_height = 123

    assert editor.remove_from_stage([wrapper.node_id])

    assert props.on_stage is False
    assert (props.stage_x, props.stage_y, props.stage_width, props.stage_height) == (40.0, 40.0, 321, 123)
    assert editor.remove_from_stage([wrapper.node_id]) is False


def test_stage_takes_annotation_edges_only(graph_with_library_system):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    from haywire.barn.builtin.nodes.annotation import AnnotationNode
    from haywire.core.graph.stage import stage_takes_edge

    graph = graph_with_library_system
    a = graph.create_node_wrapper(AnnotationNode.class_identity.registry_key, position=(0, 0))
    b = graph.create_node_wrapper(AnnotationNode.class_identity.registry_key, position=(400, 0))
    x = graph.create_node_wrapper(TestAddFloatNode.class_identity.registry_key, position=(0, 300))
    y = graph.create_node_wrapper(TestAddFloatNode.class_identity.registry_key, position=(400, 300))
    for wrapper in (a, b, x, y):
        assert wrapper is not None

    assert stage_takes_edge(graph, a.node_id, "bottom_0", b.node_id, "top_0")
    assert not stage_takes_edge(graph, x.node_id, "result", y.node_id, "value_a")
    assert not stage_takes_edge(graph, x.node_id, "result", y.node_id, "root_in")
    assert stage_takes_edge(graph, a.node_id, "bottom_0", b.node_id, "root_in")
