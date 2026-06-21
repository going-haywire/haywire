"""Reroute node — a pass-through inserted by splitting any edge.

The node ships **port-less**: ``init()`` declares no ports. The
edge-split action (``SplitEdgeWithRerouteAction``) adds a typed inlet/outlet
under the ids below, matching the concrete ``IType`` carried by the split
edge's outlet. The worker forwards the inlet value straight to the outlet
and returns the outlet id.

Returning the outlet id is required for CONTROL reroutes (the VM uses it to
navigate the execution chain). For DATA reroutes the VM discards the return
value, so returning it is harmless. CALLBACK reroutes forward the string
listener-id through the pipe mechanism exactly like DATA reroutes.

The port-less state is legal because the node is ``NodeType.REROUTE`` — the
structural validator accepts a reroute with no ports (see
``_validate_reroute_node``). See the glossary entry "Reroute node".
"""

from __future__ import annotations

from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType


# Port ids are fixed; the type is supplied per instance by the split action.
REROUTE_INLET_ID = "in"
REROUTE_OUTLET_ID = "out"


@node(
    label="Reroute",
    description="Pass-through node for bending wires. Supports DATA, CONTROL, and CALLBACK edges.",
    search_tags=["reroute", "passthrough", "split", "wire"],
    # Deliberately no `menu`: a reroute only makes sense once configured with a
    # type by the edge-split action, so it is not offered in the canvas create
    # menu. It is created exclusively via SplitEdgeWithRerouteAction.
    menu="",
    node_type=NodeType.REROUTE,
)
class RerouteNode(BaseNode):
    """Forwards its single inlet value to its single outlet.

    Ships port-less; the split action adds the typed inlet/outlet under
    ``REROUTE_INLET_ID`` / ``REROUTE_OUTLET_ID``.
    """

    def init(self) -> None:
        # No data ports. The typed inlet/outlet are added by the edge-split
        # action (_AddReroutePortsAction) right after creation.
        pass

    def post_init(self) -> None:
        # Bind this node to its dedicated minimal skin. post_init runs on both
        # fresh creation and load (see NodeWrapper._initialize), so the binding
        # is self-contained and survives reload without being persisted. The
        # skin class is imported here (not at module top) to avoid a cycle —
        # reroute_skin imports the port-id constants from this module.
        from ..skins.reroute_skin import RerouteSkin

        self.props.skin = RerouteSkin.class_identity.registry_key

    def worker(self, context: ExecutionContext) -> str | None:
        # Forward inlet value to outlet for all FlowTypes (DATA, CONTROL, CALLBACK).
        # Returning the outlet id is required for CONTROL reroutes so the VM can
        # navigate to the next node. DATA/CALLBACK reroutes discard the return value.
        if REROUTE_INLET_ID in self.ports and REROUTE_OUTLET_ID in self.ports:
            self.out(REROUTE_OUTLET_ID, self.value(REROUTE_INLET_ID))
            return REROUTE_OUTLET_ID
        return None
