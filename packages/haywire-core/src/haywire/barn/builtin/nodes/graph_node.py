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

from typing import Any, TYPE_CHECKING

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.graph.subgraph_crossing import (
    boundary_port_id,
    card_port_id,
    enter_crossing_id,
    exit_crossing_id,
)
from haywire.core.node import node, BaseNode, NodeType
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

    #: The definition this card is subscribed to, so the subscription can be
    #: moved when the card is re-bound.
    _watched: "SubgraphDefinition | None" = None

    def init(self) -> None:
        # No ports. They mirror the Subgraph's interface ports, which post_init
        # reads once the store has restored the subgraph key.
        #
        # The role still has to be settled now: a card with no Subgraph bound
        # never reaches reconcile_interface, and structural validation reads
        # the role as the node is added.
        self._stamp_node_type()

    def post_init(self) -> None:
        self.reconcile_interface()
        self.props._subscribe_field("label", self._on_label_changed)
        self._watch_definition()

    def _watch_definition(self) -> None:
        """Follow the bound Subgraph's interface for as long as it is bound.

        The card reads the boundary, never the other way round, so this is what
        carries a port grown or removed inside the Subgraph out to the card.
        """
        definition = self.resolve_definition()
        if definition is self._watched:
            return
        if self._watched is not None:
            self._watched.unsubscribe_from_validation(self._on_definition_validated)
        if definition is not None:
            definition.subscribe_to_validation(self._on_definition_validated)
        self._watched = definition

    def _on_definition_validated(self, result: Any) -> None:
        """Reconcile when the Subgraph's own validation reports a structural change.

        A node's ports change through a rejig, which marks it dirty, so every
        interface edit arrives here. A move or a repaint does not.
        """
        if result.graph is not None and result.graph.requires_graph_reassembly():
            self.reconcile_interface()

    def _on_label_changed(self, _value: object, _old: object) -> None:
        """Rename the Subgraph to match this card.

        The card is what the user names, so the name it shows is the Subgraph's
        name everywhere else too — the level tab, the breadcrumb, and the label
        stored in the file. Clearing the label restores the class label, here
        as on the card.

        Sound only where one card owns its interior. A card standing for a
        template shared by several placements overrides this to a no-op, or
        renaming one card would rename every other card's interior with it.
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
        self._watch_definition()

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
        """Rebuild this card's pins from the Subgraph's interface ports.

        The single funnel for every interface change: a collapse, a re-bind, or
        an edit inside the Subgraph. Edges on pins that survive are preserved;
        a pin whose interface port is gone is removed, and the edges that were
        on it stay in the graph unlinked, drawn to this node's ghost pin.

        A pin this card already carries keeps the order it has — the card's pin
        order is its own (ADR 0036). Does nothing when no Subgraph is bound,
        leaving whatever pins the node already carries.
        """
        definition = self.resolve_definition()
        if definition is None:
            return

        input_node = definition.input_node
        output_node = definition.output_node

        # One rejig over every port: an interface port that disappeared must
        # lose its pin, which only happens for ports left un-re-added inside
        # the block.
        with self.rejig():
            if input_node is not None:
                for outlet in self._boundary_ports(input_node, PortType.OUTLET):
                    self._mirror(outlet, as_inlet=True)
            if output_node is not None:
                for inlet in self._boundary_ports(output_node, PortType.INLET):
                    self._mirror(inlet, as_outlet=True)

        self._stamp_node_type()

    @staticmethod
    def _boundary_ports(wrapper, port_type: PortType) -> list["DataPort"]:
        """The boundary node's interface ports on one side, in display order.

        The growing slot is left out: it is the boundary node's own port, not
        part of the interface, so it has no counterpart on the card.
        """
        from haywire.barn.builtin.types import ADD

        ports = [
            port
            for port in wrapper.node.get_ports(is_port_type=port_type, has_pin=True)
            if port.type_cls is not None and not issubclass(port.type_cls, ADD)
        ]
        return sorted(ports, key=lambda port: port.order)

    def _mirror(
        self,
        port: "DataPort",
        *,
        as_inlet: bool = False,
        as_outlet: bool = False,
    ) -> None:
        """Add this card's counterpart of one interface port.

        The pin mirrors everything the interface port presents — its name, its
        docs, the widget editing it and the value it starts at — so a Group
        wrapping a slider-constrained input offers that slider on its card. A
        pin this card already carries keeps its own order; a new one lands
        after the pins already there.
        """
        if port.type_cls is None:
            return
        kwargs: dict[str, Any] = {
            "label": port.label,
            "description": port.description,
            "flow_type": port.flow_type,
            "default": port.default,
        }
        if port.widget_key is not None:
            kwargs["widget_key"] = port.widget_key
            kwargs["widget_config"] = dict(port.widget_config)
        pin_id = card_port_id(port.id, is_inlet=as_inlet)
        if as_inlet:
            self.add(port.type_cls.as_inlet(pin_id, **kwargs))
        elif as_outlet:
            self.add(port.type_cls.as_outlet(pin_id, **kwargs))

    # =========================================================================
    # DERIVED NODE TYPE
    # =========================================================================

    def _stamp_node_type(self) -> None:
        """Take the node type from the pins this card currently carries.

        A Subgraph crossed by control flow makes the card a CONTROL node; one
        crossed only by data makes it a DATA node. Called from ``init()`` for
        the port-less answer, and again from ``reconcile_interface`` — the only
        thing that changes these pins — so the role is always settled before
        validation or assembly reads it.
        """
        control = bool(self.get_ports(is_flow_type=FlowType.CONTROL, has_pin=True))
        self.set_node_type(type(self).class_behavior.node_type if control else NodeType.DATA)

    # =========================================================================
    # ASSEMBLY
    # =========================================================================

    def on_assembly(self) -> tuple[bool, str | None]:
        """Resolve the crossings and the inward copy this card's worker follows.

        Both are fixed by the interface, so the worker becomes one dict lookup
        and a walk over pre-paired ports — no port scan, no id arithmetic.

        Returns:
            ``(False, reason)`` when no Subgraph resolves, which leaves the card
            standing for nothing.
        """
        definition = self.resolve_definition()
        if definition is None:
            key = self.subgraph_key
            return (False, f"no Subgraph is bound to this Group (key: {key or 'unset'})")

        # control_pin -> what the worker returns, for each of the two hop roles.
        crossings: dict[str, str] = {}
        for inlet in self.get_ports(is_port_type=PortType.INLET, is_flow_type=FlowType.CONTROL):
            crossings[inlet.id] = enter_crossing_id(inlet.id)
        for outlet in self.get_ports(is_port_type=PortType.OUTLET, is_flow_type=FlowType.CONTROL):
            boundary_id = boundary_port_id(outlet.id)
            if boundary_id is not None:
                crossings[exit_crossing_id(boundary_id)] = outlet.id
        self.cache.crossings = crossings

        # The inward copy a data-only card makes itself: (card inlet, boundary
        # outlet) pairs, resolved to port objects.
        input_node = definition.input_node
        pairs = []
        if input_node is not None:
            for outlet in input_node.node.get_ports(is_port_type=PortType.OUTLET, has_pin=True):
                source = self.ports.get(card_port_id(outlet.id, is_inlet=True))
                if source is not None:
                    pairs.append((source, outlet))
        self.cache.inward = pairs

        return (True, None)

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
        # Hot path: one lookup into the map on_assembly() resolved. A data-only
        # card has no crossings, so it falls straight through to the copy.
        crossing = self.cache.crossings.get(context.control_pin)
        if crossing is not None:
            return crossing

        for source, target in self.cache.inward:
            target.set_value(source.get_value())
        return None
