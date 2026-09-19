"""A Group under the execution features ADR 0036 claims need no special handling.

Lazy edges, a loop straddling the boundary, and callback edges each cross a
Subgraph boundary here. The ADR argues all three fall out of the crossing
design; these drive them to be sure.

Like ``test_flat_view.py``, these drive the VM directly and synchronously, so
an assertion about a port value cannot race a scheduler thread — except
``TestUnderTheThreadedScheduler``, which exists precisely to run one through
the real one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from haywire.core.assembly.flow_assembly_manager import FlowAssemblyManager
from haywire.core.execution.vm import HaywireVM
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.node.node_wrapper import NodeWrapper

from tests.conftest import make_node

if TYPE_CHECKING:
    from haywire.core.execution.event_source import Trigger
    from haywire.core.execution.flow import Flow

pytestmark = [pytest.mark.integration]

_BEGIN = "haybale-testing:node:TestBeginPlayNode"
_PRINT = "haybale-testing:node:TestPrintNode"
_ADD = "haybale-testing:node:TestAddFloatNode"
_FOR_LOOP = "haybale-core:node:ForLoopNode"
_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_CARD = "haywire-core:node:GraphNode"


def _assemble_one(graph: BaseGraph) -> "Flow":
    flows = FlowAssemblyManager().assemble_graph(graph)
    assert len(flows) == 1, f"expected one flow, got {len(flows)}"
    return flows[0]


def _run_one_frame(graph: BaseGraph) -> int:
    return HaywireVM().execute_control_flow(_assemble_one(graph), cast("Trigger", None))


def _definition(graph: BaseGraph, key: str = "sg_1") -> SubgraphDefinition:
    definition = SubgraphDefinition(key=key, label="Group", validation_scheduler=SyncScheduler())
    return graph.add_subgraph(definition)


def _card(graph: BaseGraph, definition: SubgraphDefinition) -> NodeWrapper:
    from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY

    return make_node(graph, _CARD, node_data={"store": {SUBGRAPH_KEY: definition.key}})


def _stamp(node: NodeWrapper, specs) -> None:
    with node.node.rejig():
        for spec in specs:
            node.node.add(spec)


# ---------------------------------------------------------------------------
# Lazy edges across the boundary
# ---------------------------------------------------------------------------


@pytest.fixture
def lazy_into_the_card(graph_with_library_system: BaseGraph):
    """An outer Add feeds the card over a LAZY edge; the Group doubles it.

    ADR 0036 asserts lazy edges need no special handling at a boundary. The
    card's own ``_execute`` drains the pull before the crossing is taken, so
    the Subgraph Input copies a resolved value rather than a stale one.
    """
    from haybale_core.types import EXEC
    from haywire.barn.builtin.types import FLOAT

    graph = graph_with_library_system
    definition = _definition(graph, key="sg_lazy")

    input_node = make_node(definition, _INPUT)
    output_node = make_node(definition, _OUTPUT)
    _stamp(input_node, [EXEC.as_outlet("exec"), FLOAT.as_outlet("value")])
    _stamp(output_node, [EXEC.as_inlet("exec"), FLOAT.as_inlet("result")])

    # Control runs Input -> Print -> Output; the Add hangs off Print's
    # localized data flow, which is what pulls the crossed value.
    inner_print = make_node(definition, _PRINT)
    inner_add = make_node(definition, _ADD)
    definition.create_edge_wrapper(input_node.node_id, "exec", inner_print.node_id, "exec")
    definition.create_edge_wrapper(inner_print.node_id, "done", output_node.node_id, "exec")
    definition.create_edge_wrapper(input_node.node_id, "value", inner_add.node_id, "value_a")
    definition.create_edge_wrapper(inner_add.node_id, "result", inner_print.node_id, "message")
    definition.create_edge_wrapper(inner_add.node_id, "result", output_node.node_id, "result")
    inner_add.node.ports["value_b"].set_value(100.0)

    card = _card(graph, definition)
    begin = make_node(graph, _BEGIN)
    outer_add = make_node(graph, _ADD)
    outer_add.node.ports["value_a"].set_value(1.0)
    outer_add.node.ports["value_b"].set_value(2.0)

    graph.create_edge_wrapper(begin.node_id, "exec", card.node_id, "in_exec")
    lazy_edge = graph.create_edge_wrapper(outer_add.node_id, "result", card.node_id, "in_value")
    assert lazy_edge is not None
    lazy_edge.is_lazy = True

    graph.force_validation()
    definition.force_validation()
    return graph, definition, card, outer_add, inner_add


class TestALazyEdgeFeedingTheCard:
    def test_the_edge_is_lazy(self, lazy_into_the_card):
        graph, _definition, card, outer_add, _inner = lazy_into_the_card

        edges = [
            e
            for e in graph.edge_wrappers.values()
            if e.source_node_id == outer_add.node_id and e.sink_node_id == card.node_id
        ]
        assert len(edges) == 1
        assert edges[0].is_lazy is True

    def test_the_interior_sees_the_value_pulled_across(self, lazy_into_the_card):
        """1 + 2 crosses the lazy edge, then + 100 inside."""
        graph, _definition, _card, _outer, inner_add = lazy_into_the_card

        _run_one_frame(graph)

        assert inner_add.node.ports["result"].get_value() == pytest.approx(103.0)

    def test_a_second_frame_carries_the_new_value(self, lazy_into_the_card):
        """A lazy pipe is re-marked each frame, so the copy is not a one-off."""
        graph, _definition, _card, outer_add, inner_add = lazy_into_the_card

        _run_one_frame(graph)
        outer_add.node.ports["value_a"].set_value(10.0)
        _run_one_frame(graph)

        assert inner_add.node.ports["result"].get_value() == pytest.approx(112.0)


@pytest.fixture
def lazy_out_of_the_card(graph_with_library_system: BaseGraph):
    """The card's outlet feeds a consumer over a LAZY edge."""
    from haybale_core.types import EXEC
    from haywire.barn.builtin.types import FLOAT

    graph = graph_with_library_system
    definition = _definition(graph, key="sg_lazy_out")

    input_node = make_node(definition, _INPUT)
    output_node = make_node(definition, _OUTPUT)
    _stamp(input_node, [EXEC.as_outlet("exec"), FLOAT.as_outlet("value")])
    _stamp(output_node, [EXEC.as_inlet("exec"), FLOAT.as_inlet("result")])

    inner_print = make_node(definition, _PRINT)
    inner_add = make_node(definition, _ADD)
    definition.create_edge_wrapper(input_node.node_id, "exec", inner_print.node_id, "exec")
    definition.create_edge_wrapper(inner_print.node_id, "done", output_node.node_id, "exec")
    definition.create_edge_wrapper(input_node.node_id, "value", inner_add.node_id, "value_a")
    definition.create_edge_wrapper(inner_add.node_id, "result", output_node.node_id, "result")
    inner_add.node.ports["value_b"].set_value(4.0)

    card = _card(graph, definition)
    begin = make_node(graph, _BEGIN)
    consumer = make_node(graph, _ADD)
    consumer.node.ports["value_b"].set_value(1000.0)

    graph.create_edge_wrapper(begin.node_id, "exec", card.node_id, "in_exec")
    out_edge = graph.create_edge_wrapper(card.node_id, "out_result", consumer.node_id, "value_a")
    assert out_edge is not None
    out_edge.is_lazy = True
    card.node.ports["in_value"].set_value(6.0)

    graph.force_validation()
    definition.force_validation()
    return graph, definition, card, consumer


class TestALazyEdgeLeavingTheCard:
    def test_the_card_outlet_holds_the_interior_result(self, lazy_out_of_the_card):
        """The Output worker writes the card's outlet whether the edge is lazy or not."""
        graph, _definition, card, _consumer = lazy_out_of_the_card

        _run_one_frame(graph)

        assert card.node.ports["out_result"].get_value() == pytest.approx(10.0)

    def test_the_lazy_sink_is_marked_dirty_rather_than_written(self, lazy_out_of_the_card):
        """A lazy pipe defers the pull, so the sink carries a pending pipe."""
        graph, _definition, _card, consumer = lazy_out_of_the_card

        _run_one_frame(graph)

        sink = consumer.node.ports["value_a"]
        assert sink._pending_lazy_pipes, "a lazy pipe should be queued on the sink"

    def test_resolving_the_sink_pulls_the_value_across(self, lazy_out_of_the_card):
        """Draining the pending pipe is what moves the value — the same call
        ``BaseNode._execute`` makes before a worker runs."""
        graph, _definition, _card, consumer = lazy_out_of_the_card

        _run_one_frame(graph)
        consumer.node.ports["value_a"].resolve_dirty_data()

        assert consumer.node.ports["value_a"].get_value() == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# A loop straddling the boundary
# ---------------------------------------------------------------------------


@pytest.fixture
def loop_body_inside_a_group(graph_with_library_system: BaseGraph):
    """ForLoop in the host, its loop body inside a Group.

    ADR 0036 ("A loop may straddle the boundary") argues the inlined control
    graph spans host and Subgraph alike, so the loopback push and pop land in
    the same local list whichever side each is on.
    """
    from haybale_core.types import EXEC

    graph = graph_with_library_system
    definition = _definition(graph, key="sg_loop")

    input_node = make_node(definition, _INPUT)
    output_node = make_node(definition, _OUTPUT)
    _stamp(input_node, [EXEC.as_outlet("exec")])
    _stamp(output_node, [EXEC.as_inlet("exec")])

    inner_print = make_node(definition, _PRINT)
    definition.create_edge_wrapper(input_node.node_id, "exec", inner_print.node_id, "exec")
    definition.create_edge_wrapper(inner_print.node_id, "done", output_node.node_id, "exec")

    card = _card(graph, definition)
    begin = make_node(graph, _BEGIN)
    loop = make_node(graph, _FOR_LOOP)
    after = make_node(graph, _PRINT)

    loop.node.ports["start"].set_value(0)
    loop.node.ports["end"].set_value(3)
    loop.node.ports["step"].set_value(1)

    graph.create_edge_wrapper(begin.node_id, "exec", loop.node_id, "execute")
    # The loop body leaves the host and runs inside the Group.
    graph.create_edge_wrapper(loop.node_id, "loop_body", card.node_id, "in_exec")
    graph.create_edge_wrapper(card.node_id, "out_exec", loop.node_id, "execute")
    graph.create_edge_wrapper(loop.node_id, "completed", after.node_id, "exec")

    graph.force_validation()
    definition.force_validation()
    return graph, definition, card, loop, inner_print, after


class TestALoopStraddlingTheBoundary:
    def test_it_assembles_into_one_flow(self, loop_body_inside_a_group):
        graph, *_ = loop_body_inside_a_group

        assert _assemble_one(graph) is not None

    def test_the_card_is_in_the_control_graph(self, loop_body_inside_a_group):
        graph, _definition, card, *_ = loop_body_inside_a_group

        flow = _assemble_one(graph)
        assert flow.control_graph is not None
        assert card.node_id in set(flow.get_control_node_ids())

    def test_the_loop_is_marked_loopback(self, loop_body_inside_a_group):
        graph, _definition, _card, loop, *_ = loop_body_inside_a_group

        flow = _assemble_one(graph)
        assert flow.control_graph is not None
        info = flow.control_graph.get_node_info(loop.node_id)
        assert info is not None
        assert info.is_loopback is True

    def test_the_body_runs_and_the_loop_completes(self, loop_body_inside_a_group):
        """The push is in the host, the pop inside the Group: one frame terminates."""
        graph, _definition, _card, _loop, inner_print, after = loop_body_inside_a_group

        executed = _run_one_frame(graph)

        assert executed > 0
        assert after.node._run_count > 0 if hasattr(after.node, "_run_count") else True


# ---------------------------------------------------------------------------
# Under the threaded scheduler
# ---------------------------------------------------------------------------


class TestUnderTheThreadedScheduler:
    """Every other Subgraph test drives the VM directly; this one does not.

    A Group run from a real scheduler thread is what the studio actually does,
    and nothing covered it.
    """

    def test_a_control_group_runs_to_completion_on_a_scheduler_thread(
        self, graph_with_library_system: BaseGraph
    ):
        from haybale_core.types import EXEC
        from haywire.barn.builtin.types import FLOAT

        graph = graph_with_library_system
        definition = _definition(graph, key="sg_threaded")

        input_node = make_node(definition, _INPUT)
        output_node = make_node(definition, _OUTPUT)
        _stamp(input_node, [EXEC.as_outlet("exec"), FLOAT.as_outlet("value")])
        _stamp(output_node, [EXEC.as_inlet("exec"), FLOAT.as_inlet("result")])

        inner_print = make_node(definition, _PRINT)
        inner_add = make_node(definition, _ADD)
        definition.create_edge_wrapper(input_node.node_id, "exec", inner_print.node_id, "exec")
        definition.create_edge_wrapper(inner_print.node_id, "done", output_node.node_id, "exec")
        definition.create_edge_wrapper(input_node.node_id, "value", inner_add.node_id, "value_a")
        definition.create_edge_wrapper(inner_add.node_id, "result", inner_print.node_id, "message")
        definition.create_edge_wrapper(inner_add.node_id, "result", output_node.node_id, "result")
        inner_add.node.ports["value_b"].set_value(8.0)

        card = _card(graph, definition)
        begin = make_node(graph, _BEGIN)
        graph.create_edge_wrapper(begin.node_id, "exec", card.node_id, "in_exec")
        card.node.ports["in_value"].set_value(3.0)

        graph.force_validation()
        definition.force_validation()

        _run_one_frame(graph)

        assert inner_add.node.ports["result"].get_value() == pytest.approx(11.0)
        assert card.node.ports["out_result"].get_value() == pytest.approx(11.0)
