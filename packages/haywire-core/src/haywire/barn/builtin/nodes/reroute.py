"""Reroute node — a pass-through inserted by splitting any edge.

Ships **port-less**: ``init()`` declares no ports. The edge-split action
(``SplitEdgeWithRerouteAction``) adds a typed inlet/outlet matching the concrete
``IType`` carried by the split edge's outlet. The worker forwards the inlet value
straight to the outlet and returns the outlet id.

Returning the outlet id is required for CONTROL reroutes (the VM uses it to
navigate the execution chain). For DATA reroutes the VM discards the return
value, so returning it is harmless.

CALLBACK edges are NOT supported: the flow assembly manager reads the
subscription key from the reroute outlet at wiring time — before any worker
has run to forward it — so the listener flow would never register.

The port-less state is legal because the node is ``NodeType.REROUTE`` — the
structural validator accepts a reroute with no ports (see
``_validate_reroute_node``). See the glossary entry "Reroute node".

This node lives in the framework-owned **builtin** library (not a plugin) so
headless graphs can always load reroutes without importing any display-only
library: it declares its skin by registry-key *string* on its own ``props``
bag, never importing the skin class.
"""

from __future__ import annotations

from haywire.barn.builtin.types import CHOICES
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.settings import setting
from haywire.core.settings.descriptor import UiState
from haywire.core.types.enums import PortType


@node(
    label="Reroute",
    description="Pass-through node for bending wires. Supports DATA and CONTROL edges.",
    node_type=NodeType.REROUTE,
    hidden=True,
    _is_reroute=True,
)
class RerouteNode(BaseNode):
    """Forwards its single inlet value to its single outlet.

    Ships port-less; the split action adds the typed inlet/outlet. The port ids
    are chosen by the split action, so this node discovers its ports by
    introspection rather than naming fixed ids.
    """

    # Subclasses the INHERITED bag (BaseNode.props), not NodeProperties: the
    # inherited bag is what @node's conflict check compares against, and it is
    # itself a NodeProperties subclass, so anything it declares is kept too.
    # mypy sees BaseNode.props as the `props: NodeProperties` instance
    # annotation from BaseNode's TYPE_CHECKING branch, hence the ignore.
    class props(BaseNode.props):  # type: ignore[valid-type,misc]
        """Overrides the framework ``skin`` prop; inherits every other field.

        A reroute renders in exactly one skin — that is a constraint of what the
        node IS, not a preference, so this replaces ``NodeProperties.skin``'s
        ``graph()`` mirror with a plain field: the graph's (or studio's) default
        skin must never reach a reroute, and "reset to default" returns HERE
        rather than falling to the graph tier.

        Bound by registry-key STRING, never by importing the skin class:
        importing it would pull haywire.ui + nicegui onto the headless
        execution path. The renderer resolves the key lazily at render time.
        """

        skin = setting[CHOICES](
            "haywire-core:skin:RerouteSkin",
            label="Skin",
            description="Reroute nodes always use the minimal reroute skin",
            category="appearance",
            order=10,
        )

    def init(self) -> None:
        # No data ports. The typed inlet/outlet are added by the edge-split
        # action right after creation.
        pass

    def post_init(self) -> None:
        # Whole-category chrome gating; the skin binding itself is declared on
        # the props bag above. Runs on both fresh creation and load.
        for cat in ("state", "appearance", "annotation", "layout"):
            self.props.set_ui_state_all(UiState.HIDDEN, category=cat)

    def on_startup(self, context: ExecutionContext) -> None:
        # The split action stamps exactly one inlet + one outlet. Resolve the
        # port OBJECTS once into the transient cache so worker() does a direct
        # get_value -> set_value with no per-tick dict lookup. Re-resolved each
        # run start (cache is not serialized), so a re-typed reroute stays correct.
        inlets = self.get_ports(is_port_type=PortType.INLET, has_pin=True)
        outlets = self.get_ports(is_port_type=PortType.OUTLET, has_pin=True)
        self.cache.inlet = inlets[0] if inlets else None
        self.cache.outlet = outlets[0] if outlets else None

    def worker(self, context: ExecutionContext) -> str | None:
        # Hot path: direct field read -> write, no dict lookup, no guards.
        # Returning the outlet id is required for CONTROL reroutes (VM navigation);
        # DATA discards it.
        outlet = self.cache.outlet
        if outlet is None:
            return None  # still in the port-less latent state
        outlet.set_value(self.cache.inlet.get_value())
        return outlet.id
