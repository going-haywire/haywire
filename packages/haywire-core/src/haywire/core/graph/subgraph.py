"""``SubgraphDefinition`` — the contents of one Graph-node.

A Subgraph is a graph, so it gets ``props``, ``meta``, Variables and the whole
validation pipeline for free. Being a ``BaseGraph`` is also what delivers the
``framework < subgraph < node`` settings chain: an inner node's field resolves
its graph tier by walking ``node -> wrapper -> graph -> settings_bag_for(...)``
(ADR 0022), and that graph is this definition rather than the host.

A definition holds its nodes **live**: the wrappers in ``node_wrappers`` are the
same objects the canvas draws and the VM executes (decision 9), which is what
makes error locations and live values work inside a Group with no id
translation. Its node ids are unique across the whole tree, so a flat lookup
over the tree is unambiguous — ``BaseGraph.add_subgraph`` is what enforces that
when a definition arrives from another tree.

Example::

    definition = SubgraphDefinition(key=graph.generate_unique_subgraph_key())
    graph.add_subgraph(definition)
    definition.create_node_wrapper(registry_key="lib:node:Add")
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, TYPE_CHECKING
import copy
import logging

from .base import BaseGraph
from .utils.node_remap import remap_node_ids

if TYPE_CHECKING:
    from ..node.node_wrapper import NodeWrapper
    from .scheduler import ValidationScheduler

logger = logging.getLogger(__name__)

#: Store key a Graph-node holds its Subgraph key under. Named by string so the
#: core never imports the card's class.
SUBGRAPH_KEY = "subgraph_key"


def _rebound(node_data: Mapping[str, Any], key_map: Mapping[str, str]) -> Dict[str, Any]:
    """Return ``node_data`` with a Graph-node's stored Subgraph key remapped.

    Returned unchanged when the node holds no key, or one ``key_map`` does not
    name. The copy keeps the caller's template intact for a later re-paste.
    """
    store = node_data.get("store")
    if not isinstance(store, dict):
        return dict(node_data)

    old_key = store.get(SUBGRAPH_KEY)
    if not isinstance(old_key, str) or old_key not in key_map:
        return dict(node_data)

    rebound = copy.deepcopy(dict(node_data))
    rebound["store"][SUBGRAPH_KEY] = key_map[old_key]
    return rebound


class SubgraphDefinition(BaseGraph):
    """The nodes and edges a Graph-node stands for.

    Created by the collapse action and stored in the host graph's ``subgraphs``
    table under ``key``, which is what the Graph-node references. The two
    boundary nodes inside it define the interface the Graph-node card mirrors.

    Raises:
        RuntimeError: If no settings registry is configured on the DI context —
            inherited from ``BaseGraph``, whose construction is not inert.
    """

    def __init__(
        self,
        key: str,
        label: str = "",
        validation_delay_ms: float = 50.0,
        validation_scheduler: "Optional[ValidationScheduler]" = None,
    ):
        """Initialize an empty Subgraph definition.

        Args:
            key: Stable identifier within the host graph's ``subgraphs`` table.
                Referenced by the Graph-node, so it must not change once edges
                exist.
            label: Display name for the Graph-node card and the breadcrumb.
                Defaults to ``key``.
        """
        super().__init__(
            filestem=key,
            validation_delay_ms=validation_delay_ms,
            validation_scheduler=validation_scheduler,
        )
        self.key: str = key
        self.label: str = label or key

        # Memo for graph_node_wrapper(); re-validated on every call.
        self._graph_node_id: str | None = None

    # =========================================================================
    # BOUNDARY NODES
    # =========================================================================

    @property
    def input_node(self) -> "NodeWrapper | None":
        """The Subgraph Input wrapper, or ``None`` before the interface is created."""
        return self._boundary_node(is_input=True)

    @property
    def output_node(self) -> "NodeWrapper | None":
        """The Subgraph Output wrapper, or ``None`` before the interface is created."""
        return self._boundary_node(is_input=False)

    def _boundary_node(self, is_input: bool) -> "NodeWrapper | None":
        for wrapper in self.node_wrappers.values():
            identity = wrapper.node.identity
            if identity._is_subgraph_input if is_input else identity._is_subgraph_output:
                return wrapper
        return None

    def graph_node_wrapper(self) -> "NodeWrapper | None":
        """The Graph-node in the host graph whose card this Subgraph sits behind.

        ``None`` for a definition with no host, or none of whose host nodes
        binds this key. The result is memoized and re-validated on each call, so
        the scan over the host's nodes happens once rather than once per frame.
        """
        host = self._host_graph
        if host is None:
            return None

        memo = host.get_node_wrapper(self._graph_node_id) if self._graph_node_id else None
        if memo is not None and getattr(memo.node, "subgraph_key", None) == self.key:
            return memo

        for wrapper in host.node_wrappers.values():
            if getattr(wrapper.node, "subgraph_key", None) == self.key:
                self._graph_node_id = wrapper.node_id
                return wrapper

        self._graph_node_id = None
        return None

    def content_node_wrappers(self) -> list["NodeWrapper"]:
        """Every node in this Subgraph except the two boundary nodes."""
        return [
            wrapper for wrapper in self.node_wrappers.values() if not wrapper.node.behavior.is_boundary_node
        ]

    # =========================================================================
    # INSTANTIATION
    # =========================================================================

    def instantiate(
        self,
        nodes: Mapping[str, Any],
        edges: Mapping[str, Any],
        subgraphs: Mapping[str, Any] | None = None,
    ) -> Dict[str, str]:
        """Build this Subgraph's live contents from a serialized template.

        Every node is created under a freshly minted id that is unique across
        the whole tree, and both endpoints of every edge are rewritten onto
        those ids. Call on an empty definition; existing contents are kept and
        the template is added alongside them.

        A Graph-node among the nodes gets a Subgraph of its own, instantiated
        from ``subgraphs`` under a fresh key and bound to the rebuilt card, so a
        Group nested any number of levels deep is copied whole.

        Args:
            nodes: Serialized nodes by their id in the template, in the shape
                ``NodeWrapper.serialize`` produces.
            edges: Serialized edges by their id in the template, in the shape
                ``Edge.to_dict`` produces.
            subgraphs: The template's own Subgraph definitions by key, in the
                shape :meth:`to_dict` produces. A card whose key is absent here
                is left bound to it, which the structural validator reports.

        Returns:
            The ``template id -> minted id`` map.
        """
        remap = remap_node_ids(nodes=nodes, edges=edges, mint_id=self.generate_unique_node_id)

        # Built before the nodes: a Graph-node resolves its definition from this
        # table while it is built, to mirror the boundary nodes' ports.
        key_map = self._instantiate_subgraphs(subgraphs or {})

        for old_id, node in nodes.items():
            new_id = remap.id_map[old_id]
            position = node.get("position") or [0.0, 0.0]
            try:
                self.create_node_wrapper(
                    registry_key=node["registry_key"],
                    position=(float(position[0]), float(position[1])),
                    node_data=_rebound(node.get("node_data", {}), key_map),
                    node_id=new_id,
                )
            except Exception as exc:
                logger.error(
                    f"Error instantiating node {old_id} in subgraph '{self.key}': {exc}", exc_info=True
                )

        for edge in remap.edges:
            try:
                self.create_edge_wrapper(
                    source_node_id=edge.source_node_id,
                    outlet_port_id=edge.outlet_port_id,
                    sink_node_id=edge.sink_node_id,
                    inlet_port_id=edge.inlet_port_id,
                )
            except Exception as exc:
                logger.error(
                    f"Error instantiating edge {edge.edge_id} in subgraph '{self.key}': {exc}",
                    exc_info=True,
                )

        return remap.id_map

    def _instantiate_subgraphs(self, subgraphs: Mapping[str, Any]) -> Dict[str, str]:
        """Rebuild each nested definition under a fresh key; returns ``old key -> new key``.

        Recurses through :meth:`instantiate`, so a Group nested any number of
        levels deep gets contents and ids of its own.
        """
        key_map: Dict[str, str] = {}

        for old_key, payload in subgraphs.items():
            new_key = self.generate_unique_subgraph_key()
            try:
                definition = SubgraphDefinition(key=new_key, label=payload.get("label") or new_key)
                self.add_subgraph(definition)
                definition.instantiate(
                    nodes=payload.get("nodes", {}),
                    edges=payload.get("edges", {}),
                    subgraphs=payload.get("subgraphs", {}),
                )
            except Exception as exc:
                logger.error(
                    f"Error instantiating nested subgraph '{old_key}' in '{self.key}': {exc}",
                    exc_info=True,
                )
                continue
            key_map[old_key] = new_key

        return key_map

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def to_dict(self, include_data: bool = True) -> Dict[str, Any]:
        """Return the Subgraph as a JSON-serializable dict, carrying its key and label."""
        data = super().to_dict(include_data=include_data)
        data["key"] = self.key
        data["label"] = self.label
        return data

    def load_from_dict(self, data: Dict[str, Any]) -> bool:
        """Replace this Subgraph's contents with ``data``, restoring its label.

        ``key`` is not read back: a definition's key is where the host graph's
        table put it, so the table is the authority.
        """
        self.label = data.get("label") or self.label
        return super().load_from_dict(data)

    def __repr__(self) -> str:
        return (
            f"SubgraphDefinition(key='{self.key}', label='{self.label}', "
            f"nodes={len(self.node_wrappers)}, edges={len(self.edge_wrappers)})"
        )
