"""Address a settings bag a graph's document saves by where it lives, not by the object.

An undo action outlives the bag it wrote: a node removed and restored, or an
edge revalidated, carries a new bag of the same class. ``SettingOwner`` names
the bag by its owner and accessor, so the action finds the current one each
time it runs. ``setting_owner`` builds the address for a bag in hand.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.settings.settings import Settings

#: The graph's own bags, by accessor.
_GRAPH_ACCESSORS = ("props", "meta")
#: The one bag an edge carries.
_EDGE_ACCESSOR = "style"


@dataclass(frozen=True)
class SettingOwner:
    """Where a settings bag lives in a graph: a node's bag, the graph's own, or an edge's style.

    Attributes:
        kind: Which element owns the bag.
        accessor: The bag's name on its owner: a node's bag accessor (``"props"``,
            ``"example"``), ``"props"`` or ``"meta"`` for the graph, ``"style"`` for an edge.
        owner_id: The node or edge id; ``None`` for the graph.

    Example::

        owner = setting_owner(graph, wrapper.node.props)  # SettingOwner("node", "props", node_id)
        owner.resolve(graph) is wrapper.node.props  # True while the node is in the graph

        SettingOwner(kind="graph", accessor="meta").resolve(graph) is graph.meta  # True
    """

    kind: Literal["node", "graph", "edge"]
    accessor: str
    owner_id: str | None = None

    def resolve(self, graph: BaseGraph) -> Settings | None:
        """Return the bag this names in ``graph``, or ``None`` if its owner or accessor is gone."""
        if self.kind == "graph":
            if self.accessor not in _GRAPH_ACCESSORS:
                return None
            bag: Settings = getattr(graph, self.accessor)
            return bag
        if self.owner_id is None:
            return None
        if self.kind == "edge":
            edge = graph.get_edge_wrapper(self.owner_id)
            if edge is None or self.accessor != _EDGE_ACCESSOR:
                return None
            return edge.style
        wrapper = graph.get_node_wrapper(self.owner_id)
        node = wrapper.node if wrapper is not None else None
        if node is None or self.accessor not in type(node)._settings_bags:
            return None
        node_bag: Settings = getattr(node, self.accessor)
        return node_bag


def setting_owner(graph: BaseGraph, bag: Settings) -> SettingOwner | None:
    """Return where ``bag`` lives in ``graph``, or ``None`` for a bag the graph's document does not save.

    Matched by identity: a bag of the same class on another graph, a removed
    node or a detached edge gives ``None``, as does a standalone bag such as a
    multi-selection's form.
    """
    from haywire.core.node.promotion import bag_accessor

    for accessor in _GRAPH_ACCESSORS:
        if getattr(graph, accessor) is bag:
            return SettingOwner(kind="graph", accessor=accessor)

    node = getattr(bag, "_node", None)
    if node is not None:
        wrapper = getattr(node, "wrapper", None)
        if wrapper is None:
            return None
        node_id: str = wrapper.node_id
        if graph.get_node_wrapper(node_id) is not wrapper:
            return None
        node_accessor = bag_accessor(node, bag)
        return None if node_accessor is None else SettingOwner("node", node_accessor, node_id)

    edge = getattr(bag, "_edge", None)
    if edge is None or edge.style is not bag:
        return None
    edge_id: str = edge.edge_id
    if graph.get_edge_wrapper(edge_id) is not edge:
        return None
    return SettingOwner("edge", _EDGE_ACCESSOR, edge_id)
