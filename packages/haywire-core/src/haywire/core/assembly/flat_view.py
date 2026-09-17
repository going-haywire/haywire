"""``FlatGraphView`` — the host graph and its Subgraphs, seen as one graph.

A facade the assembly builders are handed in place of the graph, so a Subgraph's
nodes take part in the host's flows without anything downstream knowing they sit
in another graph. It is a **lookup shim over live objects**, never a copy: the
wrappers it returns are the same ones the canvas draws and the VM executes, so
error locations and live values inside a closed Group need no translation.

It answers three questions differently from a plain graph:

- ``get_node_wrapper`` searches the whole Subgraph tree, not just the host.
- ``control_transitions`` adds the **virtual crossings** at a Subgraph boundary.
  A Graph-node card and its Subgraph are separate graphs with no edge between
  them, so a crossing is a string rather than an edge — see
  ``haywire.core.graph.subgraph_crossing``.
- ``_get_edge_wrappers_for_port`` reports a **spliced** edge where a data-only
  Subgraph's crossing would otherwise break the dependency chain, so the
  topological sort orders the card before the interior and the interior before
  the consumer.

Everything else passes through to the host. Step 2's tree-wide unique node ids
are what make the lookups a flat dict search with nothing to namespace.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, TYPE_CHECKING
import logging

from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.graph.subgraph_crossing import (
    boundary_port_id,
    card_port_id,
    enter_crossing_id,
    exit_crossing_id,
)
from haywire.core.types.enums import FlowType, PortType

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.node.node_wrapper import NodeWrapper

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SplicedEdge:
    """An edge endpoint pair standing in for a Subgraph crossing.

    The assembly builders read only these four ids off an edge — they
    backpropagate on ``source_node_id`` and order on ``sink_node_id`` — so a
    crossing that has no real edge is reported as one of these. It carries no
    adapter chain and no pipe: values cross by worker copy, and this exists only
    so the dependency graph is connected.
    """

    source_node_id: str
    outlet_port_id: str
    sink_node_id: str
    inlet_port_id: str


class FlatGraphView:
    """The host graph plus every Subgraph beneath it, as the builders see it.

    Wrap the graph once, at the top of assembly::

        flows = FlowAssemblyManager().assemble_graph(graph)   # wraps internally

    Transparent for a graph with no Subgraph: every method then answers exactly
    as the host would.
    """

    def __init__(self, host: "BaseGraph"):
        self._host = host

    # =========================================================================
    # PASS-THROUGH
    # =========================================================================

    def __getattr__(self, name: str) -> Any:
        """Forward anything not overridden to the host graph.

        Keeps the facade to the three questions it actually changes, rather than
        restating ``BaseGraph``'s surface.
        """
        return getattr(self._host, name)

    # =========================================================================
    # TREE-WIDE NODE LOOKUP
    # =========================================================================

    def get_node_wrapper(self, node_id: str) -> "NodeWrapper | None":
        """Return the live wrapper for ``node_id`` from anywhere in the tree."""
        return _find_in_tree(self._host, node_id)

    def list_node_wrappers(self) -> List["NodeWrapper"]:
        """Every node in the tree, host and Subgraphs alike."""
        wrappers: List["NodeWrapper"] = []
        _collect_tree(self._host, wrappers)
        return wrappers

    # =========================================================================
    # CONTROL TOPOLOGY, WITH CROSSINGS
    # =========================================================================

    def control_transitions(self, node_id: str) -> Dict[str, Tuple[str, str]]:
        """Where control leaves ``node_id``, with Subgraph crossings spliced in.

        Three nodes get transitions a plain graph cannot see:

        - a **Graph-node**, one ``enter_`` crossing per control inlet, carrying
          control to its Subgraph Input;
        - a **Subgraph Input**, its real outlets, resolved against the
          Subgraph's own edges;
        - a **Subgraph Output**, one ``exit_`` crossing per control inlet,
          carrying control back to the card.

        Every other node is answered by its owning graph unchanged.
        """
        wrapper = self.get_node_wrapper(node_id)
        if wrapper is None:
            return {}

        owner = wrapper.graph
        transitions = owner.control_transitions(node_id) if owner is not None else {}

        definition = _subgraph_of(wrapper)
        if definition is not None:
            transitions.update(self._enter_crossings(wrapper, definition))
            return transitions

        if isinstance(owner, SubgraphDefinition) and wrapper.node.identity._is_subgraph_output:
            transitions.update(self._exit_crossings(wrapper, owner))

        return transitions

    def _enter_crossings(
        self, card: "NodeWrapper", definition: SubgraphDefinition
    ) -> Dict[str, Tuple[str, str]]:
        """One crossing per control inlet on the card, into the Subgraph Input."""
        input_node = definition.input_node
        if input_node is None:
            return {}

        crossings: Dict[str, Tuple[str, str]] = {}
        inlets = card.node.get_ports(is_port_type=PortType.INLET, is_flow_type=FlowType.CONTROL)
        for inlet in inlets:
            crossing = enter_crossing_id(inlet.id)
            crossings[crossing] = (input_node.node_id, crossing)
        return crossings

    def _exit_crossings(
        self, output_node: "NodeWrapper", definition: SubgraphDefinition
    ) -> Dict[str, Tuple[str, str]]:
        """One crossing per control inlet on the Subgraph Output, back to the card."""
        card = definition.graph_node_wrapper()
        if card is None:
            return {}

        crossings: Dict[str, Tuple[str, str]] = {}
        inlets = output_node.node.get_ports(is_port_type=PortType.INLET, is_flow_type=FlowType.CONTROL)
        for inlet in inlets:
            crossing = exit_crossing_id(inlet.id)
            crossings[crossing] = (card.node_id, crossing)
        return crossings

    # =========================================================================
    # DATA DEPENDENCIES, WITH CROSSINGS
    # =========================================================================

    def _get_edge_wrappers_for_port(self, node_id: str, port_id: str) -> List[Any]:
        """Edges on one port, with a data-only Subgraph's crossings spliced in.

        Three splices, all for ordering and reachability — never for values:

        - **an inlet fed by a card's outlet** is reported as fed by that
          Subgraph's Output, so backpropagation walks into the interior instead
          of stopping at the card;
        - **an inner inlet fed by the Subgraph Input** is reported as fed by the
          **card**, so the walk carries on out to the card's own producers and
          the card is what the interior depends on;
        - **a card's outlet** also reports the edges leaving the Subgraph Input,
          re-sourced to the card, which is what orders the card — and so the
          inward copy — before the interior that consumes it.

        A Subgraph crossed by control needs none of them: its card and boundary
        nodes are control nodes, so the interior is reached through the control
        graph and each interior control node gets its own data flow.
        """
        wrapper = self.get_node_wrapper(node_id)
        if wrapper is None:
            return []

        owner = wrapper.graph
        edges: List[Any] = list(owner._get_edge_wrappers_for_port(node_id, port_id)) if owner else []

        # Only an edge whose INLET end is the port being asked about has its
        # source rewritten. On an outlet query the near end is the source, and
        # rewriting the far end there would point the edge back at this node.
        spliced: List[Any] = [
            self._reroute_source(edge, node_id, port_id)
            if edge.sink_node_id == node_id and edge.inlet_port_id == port_id
            else edge
            for edge in edges
        ]

        definition = _subgraph_of(wrapper)
        if definition is not None and not _is_control_crossed(wrapper):
            spliced.extend(self._interior_sinks(wrapper, definition, port_id))

        return spliced

    def _reroute_source(self, edge: Any, node_id: str, port_id: str) -> Any:
        """Report an edge across a data-only Subgraph boundary from its real source.

        Returned unchanged unless the edge's source is a card or a Subgraph
        Input whose Subgraph is crossed by data alone.
        """
        source = self.get_node_wrapper(edge.source_node_id)
        if source is None:
            return edge

        # A card's outlet is written by its Subgraph Output, so that is what a
        # consumer depends on.
        definition = _subgraph_of(source)
        if definition is not None and not _is_control_crossed(source):
            output_node = definition.output_node
            boundary_id = boundary_port_id(edge.outlet_port_id)
            if output_node is not None and boundary_id is not None:
                return SplicedEdge(
                    source_node_id=output_node.node_id,
                    outlet_port_id=boundary_id,
                    sink_node_id=node_id,
                    inlet_port_id=port_id,
                )
            return edge

        # A Subgraph Input's outlet is written by the card, so that is what an
        # interior node depends on.
        if not source.node.identity._is_subgraph_input:
            return edge
        owner = source.graph
        if not isinstance(owner, SubgraphDefinition):
            return edge
        card = owner.graph_node_wrapper()
        if card is None or _is_control_crossed(card):
            return edge

        return SplicedEdge(
            source_node_id=card.node_id,
            outlet_port_id=card_port_id(edge.outlet_port_id, is_inlet=True),
            sink_node_id=node_id,
            inlet_port_id=port_id,
        )

    def _interior_sinks(
        self, card: "NodeWrapper", definition: SubgraphDefinition, port_id: str
    ) -> List[SplicedEdge]:
        """The interior nodes the Subgraph Input feeds, reported as fed by the card.

        Reported under every data outlet of the card rather than one of them:
        the topological sort counts in-degree and walks adjacency in the same
        pass, so a repeated edge increments and decrements alike and the extra
        copies cancel.
        """
        input_node = definition.input_node
        outlet = card.node.ports.get(port_id)
        if input_node is None or outlet is None or not outlet.is_outlet():
            return []

        spliced: List[SplicedEdge] = []
        for inner_outlet in input_node.node.get_ports(is_port_type=PortType.OUTLET, has_pin=True):
            for edge in definition._get_edge_wrappers_for_port(input_node.node_id, inner_outlet.id):
                if edge.source_node_id != input_node.node_id:
                    continue
                spliced.append(
                    SplicedEdge(
                        source_node_id=card.node_id,
                        outlet_port_id=port_id,
                        sink_node_id=edge.sink_node_id,
                        inlet_port_id=edge.inlet_port_id,
                    )
                )
        return spliced


# ---------------------------------------------------------------------------
# Tree helpers
# ---------------------------------------------------------------------------


def _find_in_tree(graph: "BaseGraph", node_id: str) -> "NodeWrapper | None":
    wrapper = graph.node_wrappers.get(node_id)
    if wrapper is not None:
        return wrapper
    for definition in graph.subgraphs.values():
        found = _find_in_tree(definition, node_id)
        if found is not None:
            return found
    return None


def _collect_tree(graph: "BaseGraph", into: List["NodeWrapper"]) -> None:
    into.extend(graph.node_wrappers.values())
    for definition in graph.subgraphs.values():
        _collect_tree(definition, into)


def _subgraph_of(wrapper: "NodeWrapper") -> SubgraphDefinition | None:
    """The Subgraph a Graph-node stands for, or ``None`` if it is not one."""
    resolve = getattr(wrapper.node, "resolve_definition", None)
    if resolve is None:
        return None
    definition = resolve()
    return definition if isinstance(definition, SubgraphDefinition) else None


def _is_control_crossed(card: "NodeWrapper") -> bool:
    """Whether control crosses this Graph-node's boundary, rather than data alone."""
    return bool(card.node.get_ports(is_flow_type=FlowType.CONTROL, has_pin=True))
