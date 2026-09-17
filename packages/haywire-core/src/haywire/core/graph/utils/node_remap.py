"""Re-key a serialized node/edge set onto fresh node ids.

The primitive behind both paste and Subgraph instantiation: mint one new node id
per serialized node, then rewrite both endpoints of every edge through the
resulting ``old id -> new id`` map. Nothing here touches a graph — the caller
decides what to build from the result.

Example::

    remap = remap_node_ids(
        nodes=payload["nodes"],
        edges=payload["edges"],
        mint_id=graph.generate_unique_node_id,
    )
    for old_id, new_id in remap.id_map.items():
        ...  # build the node under new_id
    for edge in remap.edges:
        ...  # build the edge between edge.source_node_id and edge.sink_node_id
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from haywire.ui.utils import generate_edge_uuid


@dataclass(frozen=True)
class RemappedEdge:
    """One edge with both endpoints rewritten to the new node ids."""

    edge_id: str
    source_node_id: str
    outlet_port_id: str
    sink_node_id: str
    inlet_port_id: str
    edge_type: str
    """The ``FlowType`` value as serialized, e.g. ``"data"``."""
    is_lazy: bool = False
    chain_adapter_keys: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NodeIdRemap:
    """The result of re-keying a node/edge set.

    ``id_map`` keys follow the iteration order of the ``nodes`` mapping passed
    in, so a caller that builds nodes in that order keeps the source order.
    """

    id_map: dict[str, str]
    edges: list[RemappedEdge]

    @property
    def new_node_ids(self) -> list[str]:
        """The minted ids, in the order the source nodes were iterated."""
        return list(self.id_map.values())


def remap_node_ids(
    nodes: Mapping[str, Any],
    edges: Mapping[str, Any],
    mint_id: Callable[[str], str],
) -> NodeIdRemap:
    """Mint a fresh id for every node in ``nodes`` and rewrite ``edges`` onto them.

    An edge whose source or sink is absent from ``nodes`` is dropped: both
    endpoints must be re-keyed for the edge to mean anything in its new home.

    Args:
        nodes: Serialized nodes by their current id, each carrying a
            ``registry_key`` (the shape ``NodeWrapper.serialize`` produces).
        edges: Serialized edges by their current id, each in the shape
            ``Edge.to_dict`` produces.
        mint_id: Returns an id unused by the destination graph, given a
            ``registry_key`` to derive the prefix from. Called once per node;
            a returned id already minted in this call is retried, so a minter
            that only knows the destination graph is enough.

    Returns:
        The ``old id -> new id`` map and the remapped edges.
    """
    id_map: dict[str, str] = {}
    minted: set[str] = set()

    for old_id, node in nodes.items():
        registry_key = node["registry_key"]
        new_id = mint_id(registry_key)
        # The minter only knows the destination graph, so ids minted earlier in
        # this same call are not yet visible to it.
        while new_id in minted:
            new_id = mint_id(registry_key)
        minted.add(new_id)
        id_map[old_id] = new_id

    remapped: list[RemappedEdge] = []
    for edge in edges.values():
        source = id_map.get(edge["source_node_id"])
        sink = id_map.get(edge["sink_node_id"])
        if source is None or sink is None:
            continue
        outlet = edge["outlet_port_id"]
        inlet = edge["inlet_port_id"]
        remapped.append(
            RemappedEdge(
                edge_id=generate_edge_uuid(source, outlet, sink, inlet),
                source_node_id=source,
                outlet_port_id=outlet,
                sink_node_id=sink,
                inlet_port_id=inlet,
                edge_type=edge["edge_type"],
                is_lazy=edge.get("is_lazy", False),
                chain_adapter_keys=list(edge.get("chain_adapter_keys") or []),
            )
        )

    return NodeIdRemap(id_map=id_map, edges=remapped)
