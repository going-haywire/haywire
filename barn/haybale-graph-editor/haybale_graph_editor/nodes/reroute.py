"""Reroute node — a pass-through inserted by splitting a data edge.

The node ships **port-less**: ``init()`` declares no data ports. The
edge-split action (``SplitEdgeWithRerouteAction``) adds a typed inlet/outlet
under the ids below, matching the concrete ``IType`` carried by the split
edge's outlet. The worker forwards the inlet value straight to the outlet.

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
    description="Pass-through node inserted on a data edge to bend/organize a wire.",
    search_tags=["reroute", "passthrough", "split", "wire"],
    # Deliberately no `menu`: a reroute only makes sense once configured with a
    # type by the edge-split action, so it is not offered in the canvas create
    # menu. It is created exclusively via SplitEdgeWithRerouteAction.
    menu="",
    # REROUTE is a DATA node that tolerates a port-less state until the split
    # action adds its typed inlet/outlet (see structural validator).
    node_type=NodeType.REROUTE,
)
class RerouteNode(BaseNode):
    """A DATA node that forwards its single inlet value to its single outlet.

    Ships port-less; the split action adds the typed inlet/outlet under
    ``REROUTE_INLET_ID`` / ``REROUTE_OUTLET_ID``.
    """

    def init(self) -> None:
        # No data ports. The typed inlet/outlet are added by the edge-split
        # action (_AddReroutePortsAction) right after creation.
        pass

    def worker(self, context: ExecutionContext) -> str | None:
        # Forward the inlet value straight to the outlet. Before the split
        # action configures the ports there is nothing to forward.
        if REROUTE_INLET_ID in self.ports and REROUTE_OUTLET_ID in self.ports:
            self.out(REROUTE_OUTLET_ID, self.value(REROUTE_INLET_ID))
        return None
