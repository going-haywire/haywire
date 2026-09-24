"""Collapse a selection into a Group, expand it back, and undo either."""

from __future__ import annotations

import pytest

from haywire.barn.builtin.nodes.graph_node import GraphNode
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.graph.subgraph_collapse import check_convex, derive_interface
from haywire.core.node.node_wrapper import NodeWrapper
from haywire.core.types.enums import PortType
from haywire.core.undo.actions.graph_actions import (
    CollapseToGraphNodeAction,
    ExpandGraphNodeAction,
)

from tests.conftest import make_node

_PRINT = "haybale-testing:node:TestPrintNode"
_ADD = "haybale-testing:node:TestAddFloatNode"
_BEGIN = "haybale-testing:node:TestBeginPlayNode"
_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_CARD = "haywire-core:node:GraphNode"


def _bound_key(graph: BaseGraph, node_id: str) -> str:
    """The Subgraph key the card ``node_id`` is bound to."""
    wrapper = graph.get_node_wrapper(node_id)
    assert wrapper is not None
    key = getattr(wrapper.node, "subgraph_key", None)
    assert isinstance(key, str)
    return key


def _collapse(graph: BaseGraph, node_ids, label: str = "Group") -> CollapseToGraphNodeAction:
    action = CollapseToGraphNodeAction(
        graph=graph,
        node_ids=list(node_ids),
        card_registry_key=_CARD,
        input_registry_key=_INPUT,
        output_registry_key=_OUTPUT,
        label=label,
    )
    action.execute()
    return action


def _editor(graph: BaseGraph, library_system):
    """An ``Editor`` over ``graph``, wired to the loaded library system's factory."""
    from haywire.core.graph.editor import Editor

    return Editor(graph, library_system.get_node_factory())


def _snapshot(graph: BaseGraph) -> tuple[set[str], set[tuple[str, str, str, str]]]:
    """The graph's nodes and its edges as endpoint tuples."""
    nodes = set(graph.node_wrappers)
    edges = {
        (e.source_node_id, e.outlet_port_id, e.sink_node_id, e.inlet_port_id)
        for e in graph.edge_wrappers.values()
    }
    return nodes, edges


# ---------------------------------------------------------------------------
# Convexity
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestConvexity:
    def test_a_chain_selected_whole_is_convex(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        a, b, c = (make_node(graph, _PRINT) for _ in range(3))
        graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
        graph.create_edge_wrapper(b.node_id, "done", c.node_id, "exec")

        assert check_convex(graph, [a.node_id, b.node_id, c.node_id]) == (True, [])

    def test_skipping_the_middle_is_refused_and_names_it(self, graph_with_library_system: BaseGraph):
        """A → B → C selecting {A, C}: collapsing gives the parent G → B and B → G."""
        graph = graph_with_library_system
        a, b, c = (make_node(graph, _PRINT) for _ in range(3))
        graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
        graph.create_edge_wrapper(b.node_id, "done", c.node_id, "exec")

        is_convex, intervening = check_convex(graph, [a.node_id, c.node_id])

        assert is_convex is False
        assert intervening == [b.node_id]

    def test_two_intervening_nodes_are_both_named(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        a, b, c, d = (make_node(graph, _PRINT) for _ in range(4))
        graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
        graph.create_edge_wrapper(b.node_id, "done", c.node_id, "exec")
        graph.create_edge_wrapper(c.node_id, "done", d.node_id, "exec")

        is_convex, intervening = check_convex(graph, [a.node_id, d.node_id])

        assert is_convex is False
        assert intervening == sorted([b.node_id, c.node_id])

    def test_a_node_only_downstream_is_not_intervening(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        a, b, c = (make_node(graph, _PRINT) for _ in range(3))
        graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
        graph.create_edge_wrapper(b.node_id, "done", c.node_id, "exec")

        assert check_convex(graph, [a.node_id, b.node_id]) == (True, [])

    def test_a_single_node_is_always_convex(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        node = make_node(graph, _PRINT)

        assert check_convex(graph, [node.node_id]) == (True, [])

    def test_a_loop_wholly_inside_the_selection_is_accepted(self, graph_with_library_system: BaseGraph):
        """A cycle among selected nodes never leaves, so it cannot re-enter."""
        graph = graph_with_library_system
        a, b = make_node(graph, _PRINT), make_node(graph, _PRINT)
        graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
        graph.create_edge_wrapper(b.node_id, "done", a.node_id, "exec")

        assert check_convex(graph, [a.node_id, b.node_id]) == (True, [])


# ---------------------------------------------------------------------------
# Interface derivation
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestInterfaceDerivation:
    def test_one_outer_outlet_feeding_three_nodes_yields_one_inlet(
        self, graph_with_library_system: BaseGraph
    ):
        """Dedup by outer source — the fan-out is preserved inside."""
        graph = graph_with_library_system
        source = make_node(graph, _ADD)
        sinks = [make_node(graph, _ADD) for _ in range(3)]
        for sink in sinks:
            graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")

        plan = derive_interface(graph, [s.node_id for s in sinks])

        assert len(plan.inlets) == 1
        assert len(plan.inlets[0].inner) == 3
        assert len(plan.crossing_edge_ids) == 3

    def test_one_inner_outlet_feeding_three_nodes_yields_one_outlet(
        self, graph_with_library_system: BaseGraph
    ):
        graph = graph_with_library_system
        source = make_node(graph, _ADD)
        sinks = [make_node(graph, _ADD) for _ in range(3)]
        for sink in sinks:
            graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")

        plan = derive_interface(graph, [source.node_id])

        assert len(plan.outlets) == 1
        assert len(plan.outlets[0].outer) == 3

    def test_two_distinct_outer_sources_yield_two_inlets(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        left, right = make_node(graph, _ADD), make_node(graph, _ADD)
        inner = make_node(graph, _ADD)
        graph.create_edge_wrapper(left.node_id, "result", inner.node_id, "value_a")
        graph.create_edge_wrapper(right.node_id, "result", inner.node_id, "value_b")

        plan = derive_interface(graph, [inner.node_id])

        assert len(plan.inlets) == 2
        assert {p.port_id for p in plan.inlets} == {"value_a", "value_b"}

    def test_an_internal_edge_is_not_a_crossing(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        a, b = make_node(graph, _ADD), make_node(graph, _ADD)
        edge = graph.create_edge_wrapper(a.node_id, "result", b.node_id, "value_a")
        assert edge is not None

        plan = derive_interface(graph, [a.node_id, b.node_id])

        assert plan.internal_edge_ids == [edge.edge_id]
        assert plan.crossing_edge_ids == []

    def test_a_label_collision_is_disambiguated_by_the_inner_node(
        self, graph_with_library_system: BaseGraph
    ):
        """Two inlets both named from a ``value_a`` port get their node's label."""
        graph = graph_with_library_system
        left, right = make_node(graph, _ADD), make_node(graph, _ADD)
        first, second = make_node(graph, _ADD), make_node(graph, _ADD)
        graph.create_edge_wrapper(left.node_id, "result", first.node_id, "value_a")
        graph.create_edge_wrapper(right.node_id, "result", second.node_id, "value_a")

        plan = derive_interface(graph, [first.node_id, second.node_id])

        assert len(plan.inlets) == 2
        # Distinct ids, and neither label is the bare colliding one.
        assert len({p.port_id for p in plan.inlets}) == 2
        assert all(p.label != "Value A" for p in plan.inlets)
        assert all(p.label.endswith("Value A") for p in plan.inlets)

    def test_a_port_id_never_carries_a_dot(self, graph_with_library_system: BaseGraph):
        """``.`` is reserved for promoted settings."""
        graph = graph_with_library_system
        source = make_node(graph, _ADD)
        inner = make_node(graph, _ADD)
        graph.create_edge_wrapper(source.node_id, "result", inner.node_id, "value_a")

        plan = derive_interface(graph, [inner.node_id])

        assert all("." not in p.port_id for p in plan.inlets + plan.outlets)


# ---------------------------------------------------------------------------
# Collapse
# ---------------------------------------------------------------------------


@pytest.fixture
def chain(graph_with_library_system: BaseGraph):
    """BeginPlay → first → middle → last, with a FLOAT strand alongside.

    ``middle`` is the convex selection of one.
    """
    graph = graph_with_library_system
    begin = make_node(graph, _BEGIN)
    first = make_node(graph, _PRINT)
    middle = make_node(graph, _PRINT)
    last = make_node(graph, _PRINT)
    graph.create_edge_wrapper(begin.node_id, "exec", first.node_id, "exec")
    graph.create_edge_wrapper(first.node_id, "done", middle.node_id, "exec")
    graph.create_edge_wrapper(middle.node_id, "done", last.node_id, "exec")
    graph.force_validation()
    return graph, begin, first, middle, last


@pytest.mark.integration
class TestCollapse:
    def test_the_selection_leaves_the_host_and_a_card_arrives(self, chain):
        graph, _begin, first, middle, last = chain

        action = _collapse(graph, [middle.node_id])

        assert middle.node_id not in graph.node_wrappers
        assert action.card_node_id in graph.node_wrappers
        assert first.node_id in graph.node_wrappers
        assert last.node_id in graph.node_wrappers

    def test_the_subgraph_holds_the_selection_and_both_boundary_nodes(self, chain):
        graph, _begin, _first, middle, _last = chain

        action = _collapse(graph, [middle.node_id])
        definition = graph.get_subgraph(action.subgraph_key)

        assert definition is not None
        assert definition.input_node is not None
        assert definition.output_node is not None
        assert [w.node_id for w in definition.content_node_wrappers()] == [middle.node_id]

    def test_the_cards_pins_match_the_crossing_edges(self, chain):
        graph, _begin, _first, middle, _last = chain

        action = _collapse(graph, [middle.node_id])
        card = graph.get_node_wrapper(action.card_node_id)

        assert card is not None
        inlets = card.node.get_ports(is_port_type=PortType.INLET, has_pin=True)
        outlets = card.node.get_ports(is_port_type=PortType.OUTLET, has_pin=True)
        assert [p.id for p in inlets] == ["in_exec"]
        assert [p.id for p in outlets] == ["out_done"]

    def test_the_crossing_edges_are_rewired_to_the_card(self, chain):
        graph, _begin, first, middle, last = chain

        action = _collapse(graph, [middle.node_id])
        card_id = action.card_node_id

        endpoints = _snapshot(graph)[1]
        assert (first.node_id, "done", card_id, "in_exec") in endpoints
        assert (card_id, "out_done", last.node_id, "exec") in endpoints
        assert middle.node_id not in graph.node_wrappers

    def test_one_outer_source_feeding_two_selected_nodes_makes_one_card_edge(
        self, graph_with_library_system: BaseGraph
    ):
        """Both crossings land on the one inlet the plan minted, and yield one card edge."""
        graph = graph_with_library_system
        source = make_node(graph, _ADD)
        left, right = make_node(graph, _ADD), make_node(graph, _ADD)
        graph.create_edge_wrapper(source.node_id, "result", left.node_id, "value_a")
        graph.create_edge_wrapper(source.node_id, "result", right.node_id, "value_a")

        action = _collapse(graph, [left.node_id, right.node_id])
        card_id = action.card_node_id

        landing = [e for e in _snapshot(graph)[1] if e[2] == card_id]
        assert len(landing) == 1
        assert landing[0][:2] == (source.node_id, "result")

    def test_one_outer_sink_fed_by_two_selected_nodes_makes_one_card_edge(
        self, graph_with_library_system: BaseGraph
    ):
        """The outlet side of the same hazard: two crossings, one outer sink port."""
        graph = graph_with_library_system
        left, right = make_node(graph, _ADD), make_node(graph, _ADD)
        sink = make_node(graph, _ADD)
        graph.create_edge_wrapper(left.node_id, "result", sink.node_id, "value_a")
        graph.create_edge_wrapper(right.node_id, "result", sink.node_id, "value_a")

        action = _collapse(graph, [left.node_id, right.node_id])
        card_id = action.card_node_id

        leaving = [e for e in _snapshot(graph)[1] if e[0] == card_id]
        assert len(leaving) == 1
        assert leaving[0][2:] == (sink.node_id, "value_a")

    def test_a_non_convex_selection_is_refused_and_names_the_node(self, chain):
        graph, _begin, first, middle, last = chain

        with pytest.raises(ValueError, match=middle.node_id):
            _collapse(graph, [first.node_id, last.node_id])

    def test_a_refused_collapse_changes_nothing(self, chain):
        graph, _begin, first, _middle, last = chain
        before = _snapshot(graph)

        with pytest.raises(ValueError, match="cannot be collapsed"):
            _collapse(graph, [first.node_id, last.node_id])

        assert _snapshot(graph) == before
        assert graph.subgraphs == {}

    def test_an_empty_selection_is_refused(self, chain):
        graph = chain[0]

        with pytest.raises(ValueError, match="Nothing to collapse"):
            _collapse(graph, ["nobody"])

    def test_a_switch_keeps_both_exec_exits_on_the_card(self, graph_with_library_system: BaseGraph):
        """Multi-exit control is ordinary, not a loopback (decision 4)."""
        graph = graph_with_library_system
        begin = make_node(graph, _BEGIN)
        switch = make_node(graph, "haybale-core:node:ControlSwitch")
        on_true = make_node(graph, _PRINT)
        on_false = make_node(graph, _PRINT)
        graph.create_edge_wrapper(begin.node_id, "exec", switch.node_id, "exec")
        graph.create_edge_wrapper(switch.node_id, "true", on_true.node_id, "exec")
        graph.create_edge_wrapper(switch.node_id, "false", on_false.node_id, "exec")
        graph.force_validation()

        action = _collapse(graph, [switch.node_id])
        card = graph.get_node_wrapper(action.card_node_id)

        assert card is not None
        outlets = {p.id for p in card.node.get_ports(is_port_type=PortType.OUTLET, has_pin=True)}
        assert {"out_true", "out_false"} <= outlets

    def test_undo_restores_the_graph_exactly(self, chain):
        graph, _begin, _first, middle, _last = chain
        before = _snapshot(graph)

        action = _collapse(graph, [middle.node_id])
        action.undo()

        assert _snapshot(graph) == before
        assert graph.subgraphs == {}


# ---------------------------------------------------------------------------
# Expand
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestExpand:
    def test_collapse_then_expand_round_trips(self, chain):
        graph, _begin, _first, middle, _last = chain
        before = _snapshot(graph)

        action = _collapse(graph, [middle.node_id])
        expand = ExpandGraphNodeAction(graph=graph, node_id=action.card_node_id)
        expand.execute()

        assert _snapshot(graph) == before
        assert graph.subgraphs == {}

    def test_the_card_and_boundary_nodes_are_gone_after_expanding(self, chain):
        graph, _begin, _first, middle, _last = chain

        action = _collapse(graph, [middle.node_id])
        definition = graph.get_subgraph(action.subgraph_key)
        assert definition is not None
        boundary_ids = [definition.input_node.node_id, definition.output_node.node_id]

        ExpandGraphNodeAction(graph=graph, node_id=action.card_node_id).execute()

        assert action.card_node_id not in graph.node_wrappers
        for node_id in boundary_ids:
            assert node_id not in graph.node_wrappers

    def test_undoing_an_expand_puts_the_group_back(self, chain):
        graph, _begin, _first, middle, _last = chain

        collapse = _collapse(graph, [middle.node_id])
        collapsed = _snapshot(graph)

        expand = ExpandGraphNodeAction(graph=graph, node_id=collapse.card_node_id)
        expand.execute()
        expand.undo()

        assert _snapshot(graph) == collapsed
        assert graph.get_subgraph(collapse.subgraph_key) is not None

    def test_collapse_expand_undo_undo_returns_to_the_original(self, chain):
        graph, _begin, _first, middle, _last = chain
        before = _snapshot(graph)

        collapse = _collapse(graph, [middle.node_id])
        expand = ExpandGraphNodeAction(graph=graph, node_id=collapse.card_node_id)
        expand.execute()

        expand.undo()
        collapse.undo()

        assert _snapshot(graph) == before
        assert graph.subgraphs == {}

    def test_expanding_a_plain_node_is_refused(self, chain):
        graph, _begin, first, _middle, _last = chain

        with pytest.raises(ValueError, match="not a Graph-node"):
            ExpandGraphNodeAction(graph=graph, node_id=first.node_id)

    def test_expanding_an_unknown_node_is_refused(self, chain):
        graph = chain[0]

        with pytest.raises(ValueError, match="not found"):
            ExpandGraphNodeAction(graph=graph, node_id="nobody")


# ---------------------------------------------------------------------------
# A Group inside a Group
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestNesting:
    """A Graph-node carries its Subgraph with it when it is collapsed or expanded.

    ``resolve_definition`` reads the table of the graph that owns the node, so a
    definition left behind in the old table cannot be found by the card that
    references it: the Group can neither be entered nor expanded.
    """

    def _nest(self, chain) -> tuple[BaseGraph, CollapseToGraphNodeAction, CollapseToGraphNodeAction]:
        """Collapse ``middle``, then collapse that card together with ``last``."""
        graph, _begin, _first, middle, last = chain
        inner = _collapse(graph, [middle.node_id], label="Inner")
        outer = _collapse(graph, [inner.card_node_id, last.node_id], label="Outer")
        return graph, inner, outer

    def test_the_inner_definition_moves_into_the_outer_one(self, chain):
        graph, inner, outer = self._nest(chain)

        assert inner.subgraph_key not in graph.subgraphs
        outer_definition = graph.get_subgraph(outer.subgraph_key)
        assert outer_definition is not None
        assert inner.subgraph_key in outer_definition.subgraphs

    def test_the_inner_card_still_resolves_its_subgraph(self, chain):
        """What entering and expanding the inner Group both go through."""
        graph, inner, outer = self._nest(chain)
        outer_definition = graph.get_subgraph(outer.subgraph_key)
        assert outer_definition is not None

        card = outer_definition.get_node_wrapper(inner.card_node_id)
        assert card is not None
        assert isinstance(card.node, GraphNode)
        resolved = card.node.resolve_definition()
        assert resolved is not None
        assert resolved is outer_definition.get_subgraph(inner.subgraph_key)

    def test_the_inner_group_expands_inside_the_outer_one(self, chain):
        graph, inner, outer = self._nest(chain)
        outer_definition = graph.get_subgraph(outer.subgraph_key)
        assert outer_definition is not None

        ExpandGraphNodeAction(graph=outer_definition, node_id=inner.card_node_id).execute()

        assert inner.card_node_id not in outer_definition.node_wrappers
        assert outer_definition.subgraphs == {}

    def test_expanding_the_outer_group_brings_the_inner_definition_back(self, chain):
        graph, inner, outer = self._nest(chain)

        ExpandGraphNodeAction(graph=graph, node_id=outer.card_node_id).execute()

        definition = graph.get_subgraph(inner.subgraph_key)
        assert definition is not None
        card = graph.get_node_wrapper(inner.card_node_id)
        assert card is not None
        assert isinstance(card.node, GraphNode)
        assert card.node.resolve_definition() is definition

    def test_undoing_the_outer_collapse_puts_the_inner_definition_back(self, chain):
        graph, inner, outer = self._nest(chain)

        outer.undo()

        assert graph.get_subgraph(inner.subgraph_key) is not None

    def test_undoing_the_outer_expand_takes_it_in_again(self, chain):
        graph, inner, outer = self._nest(chain)

        expand = ExpandGraphNodeAction(graph=graph, node_id=outer.card_node_id)
        expand.execute()
        expand.undo()

        assert inner.subgraph_key not in graph.subgraphs
        outer_definition = graph.get_subgraph(outer.subgraph_key)
        assert outer_definition is not None
        assert inner.subgraph_key in outer_definition.subgraphs

    def test_both_collapses_undo_back_to_the_original_graph(self, chain):
        graph, _begin, _first, _middle, _last = chain
        before = _snapshot(graph)

        _graph, inner, outer = self._nest(chain)
        outer.undo()
        inner.undo()

        assert _snapshot(graph) == before
        assert graph.subgraphs == {}

    def test_the_nesting_survives_a_save_and_load(self, chain):
        """``to_dict`` walks the tables, so the file follows wherever they point."""
        from haywire.core.graph.scheduler import SyncScheduler

        graph, inner, outer = self._nest(chain)
        payload = graph.to_dict(include_data=True)

        reloaded = BaseGraph(filestem="reloaded", validation_scheduler=SyncScheduler())
        reloaded.load_from_dict(payload)

        outer_definition = reloaded.get_subgraph(outer.subgraph_key)
        assert outer_definition is not None
        assert inner.subgraph_key in outer_definition.subgraphs
        assert inner.subgraph_key not in reloaded.subgraphs


# ---------------------------------------------------------------------------
# Delete and copy filtering
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestBoundaryNodeFiltering:
    def _group(self, graph: BaseGraph, chain) -> tuple[SubgraphDefinition, NodeWrapper, NodeWrapper]:
        """Collapse the chain's middle node and return the Subgraph with its interface."""
        action = _collapse(graph, [chain[3].node_id])
        definition = graph.get_subgraph(action.subgraph_key)
        assert definition is not None
        input_node, output_node = definition.input_node, definition.output_node
        assert input_node is not None
        assert output_node is not None
        return definition, input_node, output_node

    def test_deleting_everything_inside_leaves_the_interface_standing(self, chain, library_system):
        graph = chain[0]
        definition, input_node, output_node = self._group(graph, chain)

        editor = _editor(definition, library_system)
        editor.remove_elements(list(definition.node_wrappers), [])

        assert definition.content_node_wrappers() == []
        assert definition.get_node_wrapper(input_node.node_id) is not None
        assert definition.get_node_wrapper(output_node.node_id) is not None

    def test_deleting_only_the_boundary_nodes_removes_nothing(self, chain, library_system):
        graph = chain[0]
        definition, input_node, output_node = self._group(graph, chain)
        before = set(definition.node_wrappers)

        editor = _editor(definition, library_system)
        removed = editor.remove_elements([input_node.node_id, output_node.node_id], [])

        assert removed is False
        assert set(definition.node_wrappers) == before

    def test_copying_a_selection_with_them_yields_a_payload_without_them(self, chain):
        from haywire.core.graph.clipboard import build_clipboard_payload

        graph = chain[0]
        definition, input_node, output_node = self._group(graph, chain)

        payload = build_clipboard_payload(
            definition,
            list(definition.node_wrappers),
            list(definition.edge_wrappers),
            "sess",
        )

        assert input_node.node_id not in payload["nodes"]
        assert output_node.node_id not in payload["nodes"]
        assert set(payload["nodes"]) == {w.node_id for w in definition.content_node_wrappers()}


@pytest.mark.integration
class TestBoundaryNodePlacement:
    """The interface flanks the contents; two cards at the canvas default is the bug."""

    def _positions(self, graph: BaseGraph, node_ids):
        action = _collapse(graph, node_ids)
        definition = graph.get_subgraph(action.subgraph_key)
        assert definition is not None
        input_node, output_node = definition.input_node, definition.output_node
        assert input_node is not None
        assert output_node is not None
        return definition, input_node.node.props.get_position(), output_node.node.props.get_position()

    def test_the_two_boundary_nodes_do_not_share_a_position(self, chain):
        graph, _begin, _first, middle, _last = chain

        _definition, input_pos, output_pos = self._positions(graph, [middle.node_id])

        assert input_pos != output_pos

    def test_the_input_sits_before_the_contents_and_the_output_after(self, chain):
        graph, _begin, _first, middle, _last = chain
        inner_x = middle.node.props.get_position()[0]

        _definition, input_pos, output_pos = self._positions(graph, [middle.node_id])

        assert input_pos[0] < inner_x
        assert output_pos[0] > inner_x

    def test_they_are_centred_on_the_contents(self, chain):
        graph, _begin, _first, middle, _last = chain
        inner_y = middle.node.props.get_position()[1]

        _definition, input_pos, output_pos = self._positions(graph, [middle.node_id])

        assert input_pos[1] == inner_y
        assert output_pos[1] == inner_y

    def test_a_multi_node_selection_is_flanked_by_its_bounding_box(
        self, graph_with_library_system: BaseGraph
    ):
        graph = graph_with_library_system
        left = make_node(graph, _PRINT, position=(1000.0, 500.0))
        right = make_node(graph, _PRINT, position=(1600.0, 900.0))
        graph.create_edge_wrapper(left.node_id, "done", right.node_id, "exec")
        graph.force_validation()

        _definition, input_pos, output_pos = self._positions(graph, [left.node_id, right.node_id])

        assert input_pos[0] < 1000.0
        assert output_pos[0] > 1600.0
        assert input_pos[1] == output_pos[1] == 700.0


@pytest.mark.integration
class TestBoundaryNodesCannotBeCollapsed:
    """A Group's Subgraph Input and Output are its interface, not its contents."""

    def _group(self, chain) -> tuple[BaseGraph, SubgraphDefinition]:
        graph, _begin, _first, middle, _last = chain
        action = _collapse(graph, [middle.node_id])
        definition = graph.get_subgraph(action.subgraph_key)
        assert definition is not None
        return graph, definition

    def test_collapsing_a_boundary_node_is_refused_and_names_it(self, chain):
        """The message is written to be shown to the user."""
        _graph, definition = self._group(chain)
        input_node = definition.input_node
        assert input_node is not None

        with pytest.raises(ValueError, match=input_node.node_id):
            _collapse(definition, [input_node.node_id])

    def test_a_selection_around_a_boundary_node_is_refused_too(self, chain):
        """Sweeping a marquee over the whole Subgraph must not swallow its interface."""
        _graph, definition = self._group(chain)
        inside = [w.node_id for w in definition.node_wrappers.values()]

        with pytest.raises(ValueError, match="cannot be collapsed"):
            _collapse(definition, inside)

    def test_a_refused_collapse_changes_nothing(self, chain):
        _graph, definition = self._group(chain)
        inside = [w.node_id for w in definition.node_wrappers.values()]
        before = _snapshot(definition)

        with pytest.raises(ValueError, match="cannot be collapsed"):
            _collapse(definition, inside)

        assert _snapshot(definition) == before
        assert definition.subgraphs == {}

    def test_the_contents_between_them_still_collapse(self, chain):
        """The refusal is about the boundary nodes, not about nesting."""
        _graph, definition = self._group(chain)
        contents = [w.node_id for w in definition.content_node_wrappers()]

        action = _collapse(definition, contents)

        assert action.card_node_id in definition.node_wrappers


class TestPastingAGroup:
    """Copying a Group gives the copy its own Subgraph, never a shared one.

    Two cards bound to one key make ``graph_node_wrapper()`` ambiguous, which
    silently returns control to whichever card it finds first.
    """

    @pytest.fixture
    def collapsed(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        begin = make_node(graph, _BEGIN)
        middle = make_node(graph, _PRINT)
        graph.create_edge_wrapper(begin.node_id, "exec", middle.node_id, "exec")
        graph.force_validation()

        action = _collapse(graph, [middle.node_id])
        graph.force_validation()
        return graph, action.card_node_id, action.subgraph_key

    def test_a_pasted_card_gets_its_own_definition(self, collapsed):
        from haywire.core.graph.clipboard import build_clipboard_payload
        from haywire.core.undo.actions.graph_actions import PasteClipboardAction

        graph, card_node_id, subgraph_key = collapsed

        payload = build_clipboard_payload(graph, [card_node_id], [], session_id="test")
        paste = PasteClipboardAction(graph=graph, payload=payload, paste_x=500.0, paste_y=500.0)
        paste.execute()
        graph.force_validation()

        pasted_id = paste.new_node_ids[0]
        pasted = graph.get_node_wrapper(pasted_id)
        assert pasted is not None

        assert pasted.node.subgraph_key != subgraph_key, "the pasted card shares the original's Subgraph"
        assert graph.get_subgraph(pasted.node.subgraph_key) is not None, (
            "the pasted card's Subgraph was never created"
        )

    def test_each_definition_resolves_back_to_its_own_card(self, collapsed):
        from haywire.core.graph.clipboard import build_clipboard_payload
        from haywire.core.undo.actions.graph_actions import PasteClipboardAction

        graph, card_node_id, subgraph_key = collapsed

        payload = build_clipboard_payload(graph, [card_node_id], [], session_id="test")
        paste = PasteClipboardAction(graph=graph, payload=payload, paste_x=500.0, paste_y=500.0)
        paste.execute()
        graph.force_validation()

        pasted_id = paste.new_node_ids[0]
        pasted_key = graph.get_node_wrapper(pasted_id).node.subgraph_key

        assert graph.get_subgraph(subgraph_key).graph_node_wrapper().node_id == card_node_id
        assert graph.get_subgraph(pasted_key).graph_node_wrapper().node_id == pasted_id

    def test_the_copy_carries_the_original_contents(self, collapsed):
        from haywire.core.graph.clipboard import build_clipboard_payload
        from haywire.core.undo.actions.graph_actions import PasteClipboardAction

        graph, card_node_id, subgraph_key = collapsed
        original = graph.get_subgraph(subgraph_key)
        original_keys = sorted(w.registry_key for w in original.node_wrappers.values())

        payload = build_clipboard_payload(graph, [card_node_id], [], session_id="test")
        paste = PasteClipboardAction(graph=graph, payload=payload, paste_x=500.0, paste_y=500.0)
        paste.execute()
        graph.force_validation()

        pasted_key = graph.get_node_wrapper(paste.new_node_ids[0]).node.subgraph_key
        copy = graph.get_subgraph(pasted_key)

        assert sorted(w.registry_key for w in copy.node_wrappers.values()) == original_keys
        # Contents are distinct objects under fresh ids, not the originals.
        assert set(copy.node_wrappers) & set(original.node_wrappers) == set()

    def test_undo_removes_the_pasted_definition(self, collapsed):
        from haywire.core.graph.clipboard import build_clipboard_payload
        from haywire.core.undo.actions.graph_actions import PasteClipboardAction

        graph, card_node_id, _subgraph_key = collapsed

        payload = build_clipboard_payload(graph, [card_node_id], [], session_id="test")
        paste = PasteClipboardAction(graph=graph, payload=payload, paste_x=500.0, paste_y=500.0)
        paste.execute()
        graph.force_validation()
        pasted_key = graph.get_node_wrapper(paste.new_node_ids[0]).node.subgraph_key

        paste.undo()
        graph.force_validation()

        assert graph.get_subgraph(pasted_key) is None


class TestPastingANestedGroup:
    """A Group inside a Group survives the copy, all the way down."""

    @pytest.fixture
    def nested(self, graph_with_library_system: BaseGraph):
        """A host Group whose contents include a Group of their own."""
        graph = graph_with_library_system
        begin = make_node(graph, _BEGIN)
        inner = make_node(graph, _PRINT)
        outer = make_node(graph, _PRINT)
        graph.create_edge_wrapper(begin.node_id, "exec", inner.node_id, "exec")
        graph.create_edge_wrapper(inner.node_id, "done", outer.node_id, "exec")
        graph.force_validation()

        # Collapse the inner node, then collapse the resulting card with its
        # neighbour, so the outer Subgraph holds a Graph-node of its own.
        first = _collapse(graph, [inner.node_id], label="Inner")
        graph.force_validation()
        second = _collapse(graph, [first.card_node_id, outer.node_id], label="Outer")
        graph.force_validation()

        return graph, second.card_node_id, second.subgraph_key, first.subgraph_key

    def test_the_nested_definition_is_copied_too(self, nested):
        from haywire.core.graph.clipboard import build_clipboard_payload
        from haywire.core.undo.actions.graph_actions import PasteClipboardAction

        graph, card_node_id, outer_key, inner_key = nested

        payload = build_clipboard_payload(graph, [card_node_id], [], session_id="test")
        paste = PasteClipboardAction(graph=graph, payload=payload, paste_x=800.0, paste_y=800.0)
        paste.execute()
        graph.force_validation()

        pasted = graph.get_node_wrapper(paste.new_node_ids[0])
        copied_outer = graph.get_subgraph(pasted.node.subgraph_key)
        assert copied_outer is not None

        # The copy's own card must resolve a Subgraph of its own, inside it.
        inner_cards = [
            w for w in copied_outer.node_wrappers.values() if getattr(w.node, "subgraph_key", None)
        ]
        assert len(inner_cards) == 1, "the copied Group lost its nested Graph-node"

        nested_key = inner_cards[0].node.subgraph_key
        assert nested_key != inner_key, "the nested card still points at the original definition"
        assert copied_outer.get_subgraph(nested_key) is not None, "the nested Subgraph was never copied"

    def test_every_copied_card_passes_validation(self, nested):
        from haywire.core.graph.clipboard import build_clipboard_payload
        from haywire.core.undo.actions.graph_actions import PasteClipboardAction

        graph, card_node_id, _outer_key, _inner_key = nested

        payload = build_clipboard_payload(graph, [card_node_id], [], session_id="test")
        paste = PasteClipboardAction(graph=graph, payload=payload, paste_x=800.0, paste_y=800.0)
        paste.execute()
        graph.force_validation()

        pasted = graph.get_node_wrapper(paste.new_node_ids[0])
        ok, message, _s = graph._structural.validate_node(pasted)
        assert ok, message

        copied_outer = graph.get_subgraph(pasted.node.subgraph_key)
        for wrapper in copied_outer.node_wrappers.values():
            ok, message, _s = copied_outer._structural.validate_node(wrapper)
            assert ok, f"{wrapper.node_id}: {message}"

    def test_three_levels_deep_are_all_copied(self, graph_with_library_system: BaseGraph):
        from haywire.core.graph.clipboard import build_clipboard_payload
        from haywire.core.undo.actions.graph_actions import PasteClipboardAction

        graph = graph_with_library_system
        begin = make_node(graph, _BEGIN)
        a = make_node(graph, _PRINT)
        b = make_node(graph, _PRINT)
        c = make_node(graph, _PRINT)
        graph.create_edge_wrapper(begin.node_id, "exec", a.node_id, "exec")
        graph.create_edge_wrapper(a.node_id, "done", b.node_id, "exec")
        graph.create_edge_wrapper(b.node_id, "done", c.node_id, "exec")
        graph.force_validation()

        level3 = _collapse(graph, [a.node_id], label="L3")
        graph.force_validation()
        level2 = _collapse(graph, [level3.card_node_id, b.node_id], label="L2")
        graph.force_validation()
        level1 = _collapse(graph, [level2.card_node_id, c.node_id], label="L1")
        graph.force_validation()

        payload = build_clipboard_payload(graph, [level1.card_node_id], [], session_id="test")
        paste = PasteClipboardAction(graph=graph, payload=payload, paste_x=900.0, paste_y=900.0)
        paste.execute()
        graph.force_validation()

        # Walk the copy down, asserting each level resolves its own contents.
        cursor = graph.get_subgraph(_bound_key(graph, paste.new_node_ids[0]))
        depth = 1
        while True:
            assert cursor is not None
            cards = [w for w in cursor.node_wrappers.values() if getattr(w.node, "subgraph_key", None)]
            if not cards:
                break
            nested = cursor.get_subgraph(_bound_key(cursor, cards[0].node_id))
            assert nested is not None, f"level {depth + 1} was not copied"
            cursor = nested
            depth += 1

        assert depth == 3


class TestCollapsedInterfaceIsTheUsers:
    """A collapse stamps interface ports the user may remove, around the slot."""

    @pytest.fixture
    def collapsed_with_data(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        begin = make_node(graph, _BEGIN)
        adder = make_node(graph, _ADD)
        printer = make_node(graph, _PRINT)
        graph.create_edge_wrapper(begin.node_id, "exec", printer.node_id, "exec")
        graph.create_edge_wrapper(adder.node_id, "result", printer.node_id, "message")
        graph.force_validation()

        action = _collapse(graph, [printer.node_id])
        graph.force_validation()
        return graph, graph.get_subgraph(action.subgraph_key)

    def test_the_stamped_ports_are_removable(self, collapsed_with_data):
        _graph, definition = collapsed_with_data
        from haywire.barn.builtin.types import ADD

        interface = [
            p
            for node in (definition.input_node, definition.output_node)
            for p in node.node.get_all_ports()
            if not issubclass(p.type_cls, ADD)
        ]
        assert interface, "the collapse stamped no interface"
        assert all(p.is_user_removable() for p in interface)

    def test_the_growing_slot_survives_the_collapse(self, collapsed_with_data):
        _graph, definition = collapsed_with_data
        from haywire.barn.builtin.types import ADD

        for node in (definition.input_node, definition.output_node):
            slots = [p for p in node.node.get_all_ports() if issubclass(p.type_cls, ADD)]
            assert len(slots) == 1, f"{node.node_id} lost its growing slot"
            assert not slots[0].is_user_removable()
