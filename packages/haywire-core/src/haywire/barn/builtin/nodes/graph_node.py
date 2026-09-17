"""``GraphNode`` — the card on the parent canvas that stands for a Subgraph.

Created by the collapse action, never placed from the add-node menu: a bare
Graph-node with no Subgraph behind it means nothing. It references its
``SubgraphDefinition`` by key into the host graph's ``subgraphs`` table, and
mirrors that Subgraph's boundary nodes onto its own pins — the Subgraph Input's
outlets become this node's inlets, the Subgraph Output's inlets its outlets.

The definition owns the interface's **shape**; this node owns the port
**values**, so an unconnected inlet's widget value belongs to the instance.

A card is crossed, never bypassed. In a Subgraph crossed by control the card is
visited twice: an entry hop, whose localized data flow evaluates the producers
feeding its inlets and whose worker hands control inward; and an exit hop that
returns control to the parent. In a Subgraph crossed by data alone there is no
control chain, so the card runs once and copies its inlet values inward itself.
Either way the boundary nodes carry the values — see
``haywire.core.graph.subgraph_crossing``.

Lives in the framework-owned **builtin** library so headless graphs can load a
Group without importing any display-only library.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.graph.subgraph_crossing import (
    card_port_id,
    copy_inward,
    crossed_exit_id,
    enter_crossing_id,
    is_card_inlet_id,
)
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.node.behavior import NodeBehaviorFlags
from haywire.core.types import FlowType
from haywire.core.types.enums import PortType

if TYPE_CHECKING:
    from haywire.core.graph.subgraph import SubgraphDefinition
    from haywire.core.types.port import DataPort

#: Store key holding this node's Subgraph key.
SUBGRAPH_KEY = "subgraph_key"


@node(
    label="Group",
    description="A Graph-node: one card standing for a whole Subgraph.",
    node_type=NodeType.CONTROL,
    hidden=True,
    is_mutable=True,
    _is_graph_node=True,
)
class GraphNode(BaseNode):
    """One card standing for the Subgraph stored under ``subgraph_key``.

    Ships port-less and mirrors its pins from the Subgraph's boundary nodes
    whenever the interface changes. Binding a Subgraph and reconciling the
    interface are the two things to call:

    ```python
    graph_node.bind_subgraph("subgraph_a1b2c3")   # also reconciles
    graph_node.reconcile_interface()              # after a boundary port edit
    ```

    The node type follows the interface: a Subgraph with no control crossings
    makes this a DATA node, anything else a CONTROL node.
    """

    def init(self) -> None:
        # No ports. They mirror the Subgraph's boundary nodes, which post_init
        # reads once the store has restored the subgraph key.
        pass

    def post_init(self) -> None:
        self.reconcile_interface()
        self.props._subscribe_field("label", self._on_label_changed)

    def _on_label_changed(self, _value: object, _old: object) -> None:
        """Rename the Subgraph to match this card.

        The card is what the user names, so the name it shows is the Subgraph's
        name everywhere else too — the level tab, the breadcrumb, and the label
        stored in the file. Clearing the label restores the class label, here
        as on the card.
        """
        definition = self.resolve_definition()
        if definition is not None:
            definition.label = self.display_label

    # =========================================================================
    # SUBGRAPH BINDING
    # =========================================================================

    @property
    def subgraph_key(self) -> str | None:
        """The key of the Subgraph this card stands for, or ``None`` if unbound."""
        key = self.store.get(SUBGRAPH_KEY)
        return key if isinstance(key, str) else None

    def bind_subgraph(self, key: str) -> None:
        """Point this card at the Subgraph stored under ``key`` and mirror its interface."""
        self.store[SUBGRAPH_KEY] = key
        self.reconcile_interface()

    def resolve_definition(self) -> "SubgraphDefinition | None":
        """Return the bound ``SubgraphDefinition``, or ``None`` if unbound or unknown.

        Resolved from the graph that owns this node, so a Graph-node nested
        inside a Subgraph finds its definition in that Subgraph's own table.
        """
        key = self.subgraph_key
        if key is None:
            return None
        wrapper = self.wrapper
        if wrapper is None or wrapper.graph is None:
            return None
        return wrapper.graph.get_subgraph(key)

    # =========================================================================
    # INTERFACE MIRRORING
    # =========================================================================

    def reconcile_interface(self) -> None:
        """Rebuild this card's pins from the Subgraph's boundary nodes.

        Edges on pins that survive are preserved; a pin whose boundary port is
        gone is removed along with every edge that was attached to it. Does
        nothing when no Subgraph is bound, leaving whatever pins the node
        already carries.
        """
        definition = self.resolve_definition()
        if definition is None:
            return

        input_node = definition.input_node
        output_node = definition.output_node
        before = {port.id for port in self.get_ports(has_pin=True)}

        # One rejig over every port: a boundary port that disappeared must lose
        # its pin, which only happens for ports left un-re-added inside the block.
        #
        # `slot` is handed down rather than left to the add order, because
        # re-adding an existing id preserves that port — edges and all — along
        # with the order it already had. Without it a reorder on the boundary
        # node would not reach the card.
        slot = 0
        with self.rejig():
            if input_node is not None:
                for outlet in self._boundary_ports(input_node, PortType.OUTLET):
                    self._mirror(outlet, slot, as_inlet=True)
                    slot += 1
            if output_node is not None:
                for inlet in self._boundary_ports(output_node, PortType.INLET):
                    self._mirror(inlet, slot, as_outlet=True)
                    slot += 1

        lost = before - {port.id for port in self.get_ports(has_pin=True)}
        if lost:
            self._drop_edges_on(lost)

    def _drop_edges_on(self, port_ids: set[str]) -> None:
        """Remove every edge landing on one of this node's ``port_ids``.

        Removing a port leaves its edges in the graph marked invalid, which on a
        Graph-node would draw a wire to a pin that is gone. Called after the
        ports are already removed, so the edges are found through the node
        rather than through the vanished ports.
        """
        wrapper = self.wrapper
        if wrapper is None or wrapper.graph is None:
            return
        graph = wrapper.graph
        for edge in list(graph._get_all_edges(self.node_id)):
            on_outlet = edge.source_node_id == self.node_id and edge.outlet_port_id in port_ids
            on_inlet = edge.sink_node_id == self.node_id and edge.inlet_port_id in port_ids
            if on_outlet or on_inlet:
                graph.remove_edge_wrapper(edge.edge_id)

    @staticmethod
    def _boundary_ports(wrapper, port_type: PortType) -> list["DataPort"]:
        """The boundary node's ports on one side, in display order."""
        ports = wrapper.node.get_ports(is_port_type=port_type, has_pin=True)
        return sorted(ports, key=lambda port: port.order)

    def _mirror(
        self,
        port: "DataPort",
        slot: int,
        *,
        as_inlet: bool = False,
        as_outlet: bool = False,
    ) -> None:
        """Add this card's counterpart of one boundary port, at display position ``slot``."""
        if port.type_cls is None:
            return
        kwargs = {
            "label": port.label,
            "description": port.description,
            "flow_type": port.flow_type,
            "order": slot,
        }
        pin_id = card_port_id(port.id, is_inlet=as_inlet)
        if as_inlet:
            self.add(port.type_cls.as_inlet(pin_id, **kwargs))
        elif as_outlet:
            self.add(port.type_cls.as_outlet(pin_id, **kwargs))
        # A re-added port keeps the order it already had, so set it after.
        mirrored = self.ports.get(pin_id)
        if mirrored is not None:
            mirrored.order = slot

    # =========================================================================
    # DERIVED NODE TYPE
    # =========================================================================

    @property
    def behavior(self) -> NodeBehaviorFlags:
        """This instance's behavior flags, with ``node_type`` derived from the interface.

        A Subgraph crossed by control flow makes the card a CONTROL node; one
        crossed only by data makes it a DATA node. The flag is per instance
        because the interface is, so it cannot come from the class.
        """
        flags = type(self).class_behavior
        if self.get_ports(is_flow_type=FlowType.CONTROL, has_pin=True):
            return flags
        return replace(flags, node_type=NodeType.DATA)

    def worker(self, context: ExecutionContext) -> str | None:
        """Cross the boundary, in whichever of three roles this run is.

        - **Entry hop** — entered through one of the card's own control inlets.
          Returns the virtual crossing that carries control to the Subgraph
          Input. The values are already in place: this run's localized data flow
          evaluated the producers feeding the card's inlets, and ``_execute``
          drained any lazy pull, both before this worker.
        - **Exit hop** — entered through a virtual ``exit_`` crossing from the
          Subgraph Output, which has already written the card's outlets. Returns
          the card's matching real control outlet.
        - **Data-only run** — no control chain to enter by, so the card copies
          its inlet values inward itself and returns ``None``.

        Returns the outlet or crossing to follow, or ``None`` to end the branch.
        """
        control_pin = context.control_pin

        # A data-only card runs inside some host control node's data flow, so
        # control_pin holds THAT node's inlet. Only a card with control pins of
        # its own can be in one of the two hop roles.
        if control_pin is not None and self.behavior.is_control_node:
            leaving_by = crossed_exit_id(control_pin)
            if leaving_by is not None:
                outlet_id = card_port_id(leaving_by, is_inlet=False)
                return outlet_id if outlet_id in self.ports else None

            if is_card_inlet_id(control_pin):
                return enter_crossing_id(control_pin)

        definition = self.resolve_definition()
        input_node = definition.input_node if definition is not None else None
        if input_node is not None:
            copy_inward(self, input_node.node)
        return None
