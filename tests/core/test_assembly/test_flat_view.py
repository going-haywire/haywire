"""A graph containing a Group assembles and runs like the hand-inlined equivalent.

Drives the VM directly rather than through the Interpreter: assembly and one
frame, synchronously, so an assertion about a port value cannot race a
scheduler thread.
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
    from haywire.core.execution.flow import ControlNodeInfo, Flow

pytestmark = [pytest.mark.integration]

_BEGIN = "haybale-testing:node:TestBeginPlayNode"
_PRINT = "haybale-testing:node:TestPrintNode"
_ADD = "haybale-testing:node:TestAddFloatNode"
_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_CARD = "haywire-core:node:GraphNode"


def _assemble_one(graph: BaseGraph) -> "Flow":
    """Assemble ``graph``, asserting it yields exactly one flow."""
    flows = FlowAssemblyManager().assemble_graph(graph)
    assert len(flows) == 1, f"expected one flow, got {len(flows)}"
    return flows[0]


def _node_info(graph: BaseGraph, node_id: str) -> "ControlNodeInfo":
    """The assembled flow's info for one control node, narrowed to non-Optional."""
    flow = _assemble_one(graph)
    assert flow.control_graph is not None
    info = flow.control_graph.get_node_info(node_id)
    assert info is not None, f"{node_id} is not a control node in the flow"
    return info


def _control_ids(graph: BaseGraph) -> set[str]:
    return set(_assemble_one(graph).get_control_node_ids())


def _run_one_frame(graph: BaseGraph) -> int:
    """Assemble ``graph`` and execute its single flow once."""
    return HaywireVM().execute_control_flow(_assemble_one(graph), cast("Trigger", None))


def _definition(graph: BaseGraph, key: str = "sg_1") -> SubgraphDefinition:
    definition = SubgraphDefinition(key=key, label="Group", validation_scheduler=SyncScheduler())
    return graph.add_subgraph(definition)


def _card(graph: BaseGraph, definition: SubgraphDefinition) -> NodeWrapper:
    from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY

    return make_node(graph, _CARD, node_data={"store": {SUBGRAPH_KEY: definition.key}})


def _stamp(node: NodeWrapper, specs) -> None:
    """Replace a boundary node's ports with ``specs``."""
    with node.node.rejig():
        for spec in specs:
            node.node.add(spec)


@pytest.fixture
def control_group(graph_with_library_system: BaseGraph):
    """BeginPlay → [Group: inner Print, Add] → Print, with a FLOAT crossing both ways.

    The Group's inlet is left unconnected so its own port value is the input —
    a Graph-node owns its port values (decision 11).
    """
    from haybale_core.types import EXEC
    from haywire.barn.builtin.types import FLOAT

    graph = graph_with_library_system
    definition = _definition(graph)

    # --- interface ---------------------------------------------------------
    input_node = make_node(definition, _INPUT)
    output_node = make_node(definition, _OUTPUT)
    _stamp(input_node, [EXEC.as_outlet("exec"), FLOAT.as_outlet("value")])
    _stamp(output_node, [EXEC.as_inlet("exec"), FLOAT.as_inlet("result")])

    # --- interior ----------------------------------------------------------
    inner_print = make_node(definition, _PRINT)
    add = make_node(definition, _ADD)
    definition.create_edge_wrapper(input_node.node_id, "exec", inner_print.node_id, "exec")
    definition.create_edge_wrapper(inner_print.node_id, "done", output_node.node_id, "exec")
    definition.create_edge_wrapper(input_node.node_id, "value", add.node_id, "value_a")
    definition.create_edge_wrapper(add.node_id, "result", output_node.node_id, "result")
    add.node.ports["value_b"].set_value(5.0)

    # --- host --------------------------------------------------------------
    card = _card(graph, definition)
    begin = make_node(graph, _BEGIN)
    outer_print = make_node(graph, _PRINT)
    graph.create_edge_wrapper(begin.node_id, "exec", card.node_id, "in_exec")
    graph.create_edge_wrapper(card.node_id, "out_exec", outer_print.node_id, "exec")
    card.node.ports["in_value"].set_value(7.0)

    graph.force_validation()
    definition.force_validation()
    return graph, definition, card, add, outer_print


@pytest.fixture
def data_group(graph_with_library_system: BaseGraph):
    """BeginPlay → Print, with an outer Add feeding a data-only Group feeding Print.

    No control crosses the boundary, so the card is a DATA node run once from
    Print's localized data flow and it carries the values inward itself.
    """
    from haywire.barn.builtin.types import FLOAT

    graph = graph_with_library_system
    definition = _definition(graph, key="sg_data")

    input_node = make_node(definition, _INPUT)
    output_node = make_node(definition, _OUTPUT)
    _stamp(input_node, [FLOAT.as_outlet("value")])
    _stamp(output_node, [FLOAT.as_inlet("result")])

    inner_add = make_node(definition, _ADD)
    definition.create_edge_wrapper(input_node.node_id, "value", inner_add.node_id, "value_a")
    definition.create_edge_wrapper(inner_add.node_id, "result", output_node.node_id, "result")
    inner_add.node.ports["value_b"].set_value(10.0)

    card = _card(graph, definition)
    begin = make_node(graph, _BEGIN)
    printer = make_node(graph, _PRINT)
    outer_add = make_node(graph, _ADD)
    outer_add.node.ports["value_a"].set_value(2.0)
    outer_add.node.ports["value_b"].set_value(3.0)

    graph.create_edge_wrapper(begin.node_id, "exec", printer.node_id, "exec")
    graph.create_edge_wrapper(outer_add.node_id, "result", card.node_id, "in_value")
    graph.create_edge_wrapper(card.node_id, "out_result", printer.node_id, "message")

    graph.force_validation()
    definition.force_validation()
    return graph, definition, card, outer_add, inner_add, printer


class TestDataOnlyGroup:
    def test_the_card_is_a_data_node(self, data_group):
        from haywire.core.node import NodeType

        _graph, _definition, card, _outer, _inner, _printer = data_group

        assert card.node.behavior.node_type == NodeType.DATA

    def test_the_card_is_not_in_the_control_graph(self, data_group):
        graph, _definition, card, _outer, _inner, _printer = data_group

        assert card.node_id not in _control_ids(graph)

    def test_the_whole_chain_lands_in_one_localized_data_flow_in_order(self, data_group):
        """Producers, then the card (which copies inward), then the interior."""
        graph, definition, card, outer_add, inner_add, printer = data_group

        info = _node_info(graph, printer.node_id)
        assert info.localized_data_flow is not None
        sequence = [n.node_id for n in info.localized_data_flow.execution_sequence]

        assert set(sequence) == {
            outer_add.node_id,
            card.node_id,
            inner_add.node_id,
            definition.output_node.node_id,
        }
        assert sequence.index(outer_add.node_id) < sequence.index(card.node_id)
        assert sequence.index(card.node_id) < sequence.index(inner_add.node_id)
        assert sequence.index(inner_add.node_id) < sequence.index(definition.output_node.node_id)

    def test_a_value_crosses_in_and_back_out(self, data_group):
        """2 + 3 outside, + 10 inside, back out to the card."""
        graph, _definition, card, _outer, inner_add, _printer = data_group

        _run_one_frame(graph)

        assert inner_add.node.ports["result"].get_value() == 15.0
        assert card.node.ports["out_result"].get_value() == 15.0

    def test_the_consumer_outside_receives_it(self, data_group, caplog):
        import logging

        graph, _definition, _card, _outer, _inner, printer = data_group
        printer.node.ports["prepend"].set_value("RESULT=")

        with caplog.at_level(logging.INFO, logger="haybale.testing.print"):
            _run_one_frame(graph)

        assert "RESULT=15.0" in caplog.text

    def test_a_changed_producer_value_flows_through_on_the_next_frame(self, data_group):
        graph, _definition, card, outer_add, _inner, _printer = data_group

        _run_one_frame(graph)
        outer_add.node.ports["value_a"].set_value(20.0)
        _run_one_frame(graph)

        assert card.node.ports["out_result"].get_value() == 33.0


class TestTransparency:
    def test_a_graph_with_no_subgraph_assembles_unchanged(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        begin = make_node(graph, _BEGIN)
        printer = make_node(graph, _PRINT)
        graph.create_edge_wrapper(begin.node_id, "exec", printer.node_id, "exec")
        graph.force_validation()

        flows = FlowAssemblyManager().assemble_graph(graph)

        assert len(flows) == 1
        assert set(flows[0].get_control_node_ids()) == {begin.node_id, printer.node_id}

    def test_the_view_forwards_unknown_attributes_to_the_host(self, graph_with_library_system: BaseGraph):
        from haywire.core.assembly.flat_view import FlatGraphView

        graph = graph_with_library_system
        view = FlatGraphView(graph)

        assert view.graph_id == graph.graph_id
        assert view.variables is graph.variables


class TestControlGroupAssembly:
    def test_the_card_and_both_boundary_nodes_are_in_the_control_graph(self, control_group):
        graph, definition, card, _add, outer_print = control_group

        control_ids = _control_ids(graph)

        assert card.node_id in control_ids
        assert definition.input_node.node_id in control_ids
        assert definition.output_node.node_id in control_ids
        assert outer_print.node_id in control_ids

    def test_the_interior_control_node_joins_the_host_flow(self, control_group):
        graph, definition, _card, _add, _outer = control_group

        control_ids = _control_ids(graph)

        inner = [w for w in definition.content_node_wrappers() if w.registry_key == _PRINT]
        assert len(inner) == 1
        assert inner[0].node_id in control_ids

    def test_the_card_carries_both_the_enter_crossing_and_its_real_outlet(self, control_group):
        graph, definition, card, _add, outer_print = control_group

        info = _node_info(graph, card.node_id)
        assert info.outlet_map["enter_in_exec"] == (definition.input_node.node_id, "enter_in_exec")
        assert info.outlet_map["out_exec"] == (outer_print.node_id, "exec")

    def test_the_subgraph_output_exits_back_to_the_card(self, control_group):
        graph, definition, card, _add, _outer = control_group

        info = _node_info(graph, definition.output_node.node_id)
        assert info.outlet_map["exit_exec"] == (card.node_id, "exit_exec")

    def test_the_interior_data_node_lands_in_a_localized_data_flow(self, control_group):
        graph, definition, _card, add, _outer = control_group

        info = _node_info(graph, definition.output_node.node_id)
        assert info.localized_data_flow is not None
        assert [n.node_id for n in info.localized_data_flow.execution_sequence] == [add.node_id]


class TestControlGroupExecution:
    def test_a_value_crosses_in_and_back_out(self, control_group):
        """One assertion over the whole mechanism.

        ``7.0`` on the card's unconnected inlet must reach the interior's Add,
        be summed with ``5.0``, and come back out on the card's outlet.
        """
        graph, _definition, card, _add, _outer = control_group

        _run_one_frame(graph)

        assert card.node.ports["out_result"].get_value() == 12.0

    def test_the_interior_computed_the_sum(self, control_group):
        graph, _definition, _card, add, _outer = control_group

        _run_one_frame(graph)

        assert add.node.ports["result"].get_value() == 12.0

    def test_a_changed_card_value_is_re_read_on_the_next_frame(self, control_group):
        graph, _definition, card, _add, _outer = control_group

        _run_one_frame(graph)
        card.node.ports["in_value"].set_value(1.0)
        _run_one_frame(graph)

        assert card.node.ports["out_result"].get_value() == 6.0

    def test_control_reaches_the_node_after_the_group(self, control_group, caplog):
        """The card's exit hop must continue the host chain, not end the flow."""
        import logging

        graph, _definition, _card, _add, outer_print = control_group
        outer_print.node.ports["message"].set_value("AFTER-THE-GROUP")
        outer_print.node.ports["prepend"].set_value("")

        with caplog.at_level(logging.INFO, logger="haybale.testing.print"):
            _run_one_frame(graph)

        assert "AFTER-THE-GROUP" in caplog.text

    def test_every_node_in_the_chain_executed_once(self, control_group):
        """5 control nodes (begin, card×2, input, output, inner print, outer print)
        plus the interior Add."""
        graph, _definition, _card, _add, _outer = control_group

        exec_count = _run_one_frame(graph)

        # begin + card(entry) + input + inner print + output + card(exit) + outer
        # print = 7 control executions, plus Add in the output's data flow.
        assert exec_count == 8


class TestNesting:
    """A Group inside a Group. Two boundaries, one flat flow."""

    @pytest.fixture
    def nested(self, graph_with_library_system: BaseGraph):
        from haybale_core.types import EXEC
        from haywire.barn.builtin.types import FLOAT

        graph = graph_with_library_system

        outer = _definition(graph, key="sg_outer")
        inner = SubgraphDefinition(key="sg_inner", label="Inner", validation_scheduler=SyncScheduler())
        outer.add_subgraph(inner)

        # Innermost Subgraph: adds 100.
        inner_in = make_node(inner, _INPUT)
        inner_out = make_node(inner, _OUTPUT)
        _stamp(inner_in, [EXEC.as_outlet("exec"), FLOAT.as_outlet("value")])
        _stamp(inner_out, [EXEC.as_inlet("exec"), FLOAT.as_inlet("result")])
        deep_print = make_node(inner, _PRINT)
        deep_add = make_node(inner, _ADD)
        deep_add.node.ports["value_b"].set_value(100.0)
        inner.create_edge_wrapper(inner_in.node_id, "exec", deep_print.node_id, "exec")
        inner.create_edge_wrapper(deep_print.node_id, "done", inner_out.node_id, "exec")
        inner.create_edge_wrapper(inner_in.node_id, "value", deep_add.node_id, "value_a")
        inner.create_edge_wrapper(deep_add.node_id, "result", inner_out.node_id, "result")

        # Outer Subgraph: holds the inner Group's card and passes straight through.
        outer_in = make_node(outer, _INPUT)
        outer_out = make_node(outer, _OUTPUT)
        _stamp(outer_in, [EXEC.as_outlet("exec"), FLOAT.as_outlet("value")])
        _stamp(outer_out, [EXEC.as_inlet("exec"), FLOAT.as_inlet("result")])
        inner_card = _card(outer, inner)
        outer.create_edge_wrapper(outer_in.node_id, "exec", inner_card.node_id, "in_exec")
        outer.create_edge_wrapper(inner_card.node_id, "out_exec", outer_out.node_id, "exec")
        outer.create_edge_wrapper(outer_in.node_id, "value", inner_card.node_id, "in_value")
        outer.create_edge_wrapper(inner_card.node_id, "out_result", outer_out.node_id, "result")

        # Host.
        outer_card = _card(graph, outer)
        begin = make_node(graph, _BEGIN)
        graph.create_edge_wrapper(begin.node_id, "exec", outer_card.node_id, "in_exec")
        outer_card.node.ports["in_value"].set_value(1.0)

        graph.force_validation()
        outer.force_validation()
        inner.force_validation()
        return graph, outer_card, inner_card, deep_add

    def test_both_levels_join_one_flat_control_graph(self, nested):
        graph, outer_card, inner_card, _deep_add = nested

        control_ids = _control_ids(graph)

        assert outer_card.node_id in control_ids
        assert inner_card.node_id in control_ids

    def test_a_value_crosses_two_boundaries_and_comes_back(self, nested):
        """1.0 on the outermost card, +100 two levels down, back out to the top."""
        graph, outer_card, _inner_card, deep_add = nested

        _run_one_frame(graph)

        assert deep_add.node.ports["result"].get_value() == 101.0
        assert outer_card.node.ports["out_result"].get_value() == 101.0

    def test_tree_wide_lookup_reaches_the_deepest_node(self, nested):
        from haywire.core.assembly.flat_view import FlatGraphView

        graph, _outer_card, _inner_card, deep_add = nested

        view = FlatGraphView(graph)

        assert view.get_node_wrapper(deep_add.node_id) is deep_add
        assert deep_add in view.list_node_wrappers()


@pytest.mark.integration
class TestCollapsedGroupRuns:
    """The acceptance criterion: collapsing must not change what the graph does."""

    @pytest.fixture
    def chain(self, graph_with_library_system: BaseGraph):
        """BeginPlay → first → middle → last, middle adding 5 to a FLOAT strand."""
        graph = graph_with_library_system
        begin = make_node(graph, _BEGIN)
        first = make_node(graph, _PRINT)
        middle = make_node(graph, _PRINT)
        last = make_node(graph, _PRINT)
        adder = make_node(graph, _ADD)
        adder.node.ports["value_a"].set_value(7.0)
        adder.node.ports["value_b"].set_value(5.0)

        graph.create_edge_wrapper(begin.node_id, "exec", first.node_id, "exec")
        graph.create_edge_wrapper(first.node_id, "done", middle.node_id, "exec")
        graph.create_edge_wrapper(middle.node_id, "done", last.node_id, "exec")
        graph.create_edge_wrapper(adder.node_id, "result", middle.node_id, "message")
        graph.force_validation()
        return graph, middle, last

    def _log_of_one_frame(self, graph: BaseGraph, caplog) -> str:
        import logging

        with caplog.at_level(logging.INFO, logger="haybale.testing.print"):
            _run_one_frame(graph)
        return caplog.text

    def test_behaviour_is_identical_before_and_after_collapsing(self, chain, caplog):
        from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction

        graph, middle, last = chain
        last.node.ports["message"].set_value("TAIL")
        last.node.ports["prepend"].set_value("")
        middle.node.ports["prepend"].set_value("MID=")

        before = self._log_of_one_frame(graph, caplog)
        assert "MID=12.0" in before
        assert "TAIL" in before

        caplog.clear()
        CollapseToGraphNodeAction(
            graph=graph,
            node_ids=[middle.node_id],
            card_registry_key=_CARD,
            input_registry_key=_INPUT,
            output_registry_key=_OUTPUT,
        ).execute()
        graph.force_validation()

        after = self._log_of_one_frame(graph, caplog)

        assert "MID=12.0" in after, "the collapsed node did not receive its data"
        assert "TAIL" in after, "control did not continue past the Group"
