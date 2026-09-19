"""Planning a collapse: is this selection collapsible, and what interface does it get?

Pure analysis over a graph and a set of node ids — nothing here mutates
anything. ``CollapseToGraphNodeAction`` runs ``check_convex`` first and builds
the Subgraph from ``derive_interface``.

The selection's edges are split by the clipboard's **both-endpoints rule**: an
edge is internal when both of its endpoints are selected, and crosses the
boundary when exactly one is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Sequence, Set, Tuple
import re

from ..types.enums import FlowType

if TYPE_CHECKING:
    from ..edge.edge_wrapper import EdgeWrapper
    from ..types.interface import IType
    from .base import BaseGraph

#: A port endpoint: ``(node_id, port_id)``.
Endpoint = Tuple[str, str]


# ---------------------------------------------------------------------------
# Convexity
# ---------------------------------------------------------------------------


def check_convex(graph: "BaseGraph", node_ids: Iterable[str]) -> Tuple[bool, List[str]]:
    """Return whether ``node_ids`` can be collapsed, and what would have to join them.

    A selection is **convex** when no path leaves it and re-enters. ``A -> B ->
    C`` with ``{A, C}`` selected is not: collapsing it would give the parent
    both ``G -> B`` and ``B -> G``, so the Graph-node would be entered twice in
    one pass — incoherent for control flow, and a real cycle for data.

    Both flow types count. A data path that leaves and re-enters becomes a cycle
    through the Subgraph's own contents once inlined, which the data-flow
    builder rejects at assembly.

    Args:
        node_ids: The selected nodes. Ids the graph does not know are ignored.

    Returns:
        ``(True, [])`` when convex, else ``(False, ids)`` naming every node that
        lies on a path out of the selection and back into it — the nodes the
        user would have to add. Ids are sorted, so the message is stable.
    """
    selected = {node_id for node_id in node_ids if graph.get_node_wrapper(node_id) is not None}
    if len(selected) < 2:
        return (True, [])

    successors, predecessors = _adjacency(graph)

    downstream = _walk(selected, successors, selected)
    upstream = _walk(selected, predecessors, selected)

    intervening = sorted(downstream & upstream)
    return (not intervening, intervening)


def _adjacency(graph: "BaseGraph") -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Forward and backward node adjacency over every edge in the graph."""
    successors: Dict[str, Set[str]] = {}
    predecessors: Dict[str, Set[str]] = {}
    for edge in graph.edge_wrappers.values():
        successors.setdefault(edge.source_node_id, set()).add(edge.sink_node_id)
        predecessors.setdefault(edge.sink_node_id, set()).add(edge.source_node_id)
    return successors, predecessors


def _walk(start: Set[str], adjacency: Dict[str, Set[str]], skip: Set[str]) -> Set[str]:
    """Every node reachable from ``start``, excluding ``skip`` from the result and the walk."""
    reached: Set[str] = set()
    queue = [node_id for seed in start for node_id in adjacency.get(seed, ())]
    while queue:
        node_id = queue.pop()
        if node_id in skip or node_id in reached:
            continue
        reached.add(node_id)
        queue.extend(adjacency.get(node_id, ()))
    return reached


# ---------------------------------------------------------------------------
# Interface derivation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BoundaryPort:
    """One port of the interface, and the edges it stands for.

    ``port_id`` is minted here rather than copied: a boundary port id must be
    unique on its boundary node, and the inner ports it gathers may share a
    name. Everything else is taken from the interior port that names this one,
    so an interface derived from documented nodes arrives documented — the same
    inward-to-outward seeding ``SubgraphInputNode.hb_grow`` does for a port
    grown by wiring.
    """

    port_id: str
    label: str
    itype: "type[IType]"
    flow_type: FlowType
    description: str = ""
    widget_key: "str | None" = None
    widget_config: Dict[str, Any] = field(default_factory=dict)
    default: "dict | None" = None
    """The interior port's default, so the card's pin starts where it does."""
    outer: List[Endpoint] = field(default_factory=list)
    """The endpoints outside the selection: sources for an inlet, sinks for an outlet."""
    inner: List[Endpoint] = field(default_factory=list)
    """The endpoints inside the selection: sinks for an inlet, the source for an outlet."""


@dataclass(frozen=True)
class InterfacePlan:
    """The interface a selection collapses to.

    ``inlets`` become the Subgraph Input's outlets and the card's inlets;
    ``outlets`` become the Subgraph Output's inlets and the card's outlets.
    """

    inlets: List[BoundaryPort] = field(default_factory=list)
    outlets: List[BoundaryPort] = field(default_factory=list)
    internal_edge_ids: List[str] = field(default_factory=list)
    """Edges with both endpoints selected — these move into the Subgraph."""
    crossing_edge_ids: List[str] = field(default_factory=list)
    """Edges with exactly one endpoint selected — these are rewired to the card."""


def derive_interface(graph: "BaseGraph", node_ids: Sequence[str]) -> InterfacePlan:
    """Return the interface the selection's crossing edges imply.

    Dedup follows the endpoint that makes the user's wiring survive:

    - **Inlets** group by their *outer source*. One outer outlet feeding three
      selected nodes mints **one** inlet that fans out again inside.
    - **Outlets** group by their *inner source*. One inner outlet feeding four
      nodes outside mints **one** outlet.

    Labels come from the inner port, which is what makes a pin meaningful to
    someone who did not build the Subgraph, and survives rewiring outside. On a
    collision the inner node's label is prepended (``value`` → ``Scale value``).

    A crossing edge whose port cannot be resolved is left out of the interface
    but still reported in ``crossing_edge_ids``, so a collapse drops it rather
    than silently keeping a dangling edge.
    """
    selected = set(node_ids)

    internal: List[str] = []
    crossing: List[str] = []
    inlet_groups: Dict[Endpoint, List["EdgeWrapper"]] = {}
    outlet_groups: Dict[Endpoint, List["EdgeWrapper"]] = {}

    for edge in graph.edge_wrappers.values():
        source_in = edge.source_node_id in selected
        sink_in = edge.sink_node_id in selected

        if source_in and sink_in:
            internal.append(edge.edge_id)
            continue
        if not source_in and not sink_in:
            continue

        crossing.append(edge.edge_id)
        if sink_in:
            # Enters the selection: group by the outer outlet feeding it.
            inlet_groups.setdefault((edge.source_node_id, edge.outlet_port_id), []).append(edge)
        else:
            # Leaves the selection: group by the inner outlet feeding it.
            outlet_groups.setdefault((edge.source_node_id, edge.outlet_port_id), []).append(edge)

    return InterfacePlan(
        inlets=_build_ports(graph, inlet_groups, is_inlet=True),
        outlets=_build_ports(graph, outlet_groups, is_inlet=False),
        internal_edge_ids=internal,
        crossing_edge_ids=crossing,
    )


def _build_ports(
    graph: "BaseGraph",
    groups: Dict[Endpoint, List["EdgeWrapper"]],
    *,
    is_inlet: bool,
) -> List[BoundaryPort]:
    """Turn one side's edge groups into boundary ports, with unique ids and labels.

    Each port takes its name, docs, widget and default from the one interior
    port that names it. An inlet may dedup several inner sinks — one outer
    outlet feeding three selected nodes becomes one inlet — and only the first
    of them names the port; the others' labels and widgets are not merged,
    because no combination of them reads better than one. Groups are sorted, so
    which one wins is stable across collapses of the same selection.
    """
    ports: List[BoundaryPort] = []
    taken_ids: Set[str] = set()
    label_counts: Dict[str, int] = {}

    # Sorted so a collapse of the same selection always mints the same interface.
    for endpoint in sorted(groups):
        edges = groups[endpoint]
        # The port whose type and name the boundary port takes: for an inlet the
        # first inner sink, for an outlet the inner source itself.
        naming = (
            _port_of(graph, edges[0].sink_node_id, edges[0].inlet_port_id)
            if is_inlet
            else _port_of(graph, endpoint[0], endpoint[1])
        )
        if naming is None:
            continue
        itype = naming.stored_type
        if itype is None:
            continue

        label = naming.label or naming.id
        label_counts[label] = label_counts.get(label, 0) + 1
        ports.append(
            BoundaryPort(
                port_id=_mint_port_id(naming.id, taken_ids),
                label=label,
                itype=itype,
                flow_type=naming.flow_type,
                description=naming.description,
                widget_key=naming.widget_key,
                widget_config=dict(naming.widget_config),
                default=naming.default,
                outer=[(endpoint[0], endpoint[1])]
                if is_inlet
                else [(e.sink_node_id, e.inlet_port_id) for e in edges],
                inner=[(e.sink_node_id, e.inlet_port_id) for e in edges]
                if is_inlet
                else [(endpoint[0], endpoint[1])],
            )
        )

    return _disambiguate(graph, ports, label_counts, is_inlet=is_inlet)


def _disambiguate(
    graph: "BaseGraph",
    ports: List[BoundaryPort],
    label_counts: Dict[str, int],
    *,
    is_inlet: bool,
) -> List[BoundaryPort]:
    """Prepend the inner node's label to any label two ports share."""
    from dataclasses import replace as _replace

    resolved: List[BoundaryPort] = []
    for port in ports:
        if label_counts.get(port.label, 0) < 2:
            resolved.append(port)
            continue
        node_id = port.inner[0][0] if is_inlet else port.inner[0][0]
        wrapper = graph.get_node_wrapper(node_id)
        node_label = wrapper.node.identity.label if wrapper is not None else node_id
        resolved.append(_replace(port, label=f"{node_label} {port.label}"))
    return resolved


def _port_of(graph: "BaseGraph", node_id: str, port_id: str):
    """The live ``DataPort``, or ``None`` if either the node or the port is gone."""
    wrapper = graph.get_node_wrapper(node_id)
    if wrapper is None:
        return None
    return wrapper.node.ports.get(port_id)


def _mint_port_id(seed: str, taken: Set[str]) -> str:
    """A port id derived from ``seed``, unique among ``taken``.

    ``.`` is reserved for promoted settings, so it is stripped rather than
    carried through from an inner promoted port's id.
    """
    base = re.sub(r"[^0-9A-Za-z_]", "_", seed) or "port"
    candidate = base
    suffix = 2
    while candidate in taken:
        candidate = f"{base}_{suffix}"
        suffix += 1
    taken.add(candidate)
    return candidate
