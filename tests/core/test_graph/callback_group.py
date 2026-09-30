"""A Group whose interface carries callback ports, for the edge-kinds step 4 tests.

The interface is stamped the way collapse stamps it: `sub_in` on the Subgraph
Input (card pin `in_sub_in`) and `sub_out` on the Subgraph Output (card pin
`out_sub_out`), both `CALLBACK` and `RESOLVED`, the Output's inlet relaying.
"""

from dataclasses import dataclass
from typing import Any

from tests.conftest import make_node

LISTEN = "haybale-testing:node:TestCustomCallbackNode"
EMIT = "haybale-testing:node:TestEmitCallbackNode"
INPUT = "haywire-core:node:SubgraphInputNode"
OUTPUT = "haywire-core:node:SubgraphOutputNode"
CARD = "haywire-core:node:GraphNode"


@dataclass
class CallbackGroup:
    graph: Any
    definition: Any
    input_node: Any
    output_node: Any
    card: Any = None


def subscriptions(emitter) -> list:
    """The event names an emit node would emit to."""
    return list(emitter.node.ports["edge_callback"].get_value().values())


def build_interior(graph, key: str = "sg_cb") -> CallbackGroup:
    """A Subgraph with one callback port on each boundary node, and no card yet."""
    from haybale_core.types import CALLBACK
    from haywire.core.graph.subgraph import SubgraphDefinition
    from haywire.core.graph.subgraph_crossing import RELAY_HANDLER
    from haywire.core.types.enums import PortOrigin

    definition = graph.add_subgraph(SubgraphDefinition(key=key, label="Group"))
    input_node = make_node(definition, INPUT)
    output_node = make_node(definition, OUTPUT)
    with input_node.node.rejig(exclude=[PortOrigin.DECLARED]):
        input_node.node.add(CALLBACK.as_outlet("sub_in", label="Sub in", origin=PortOrigin.RESOLVED))
    with output_node.node.rejig(exclude=[PortOrigin.DECLARED]):
        output_node.node.add(
            CALLBACK.as_inlet(
                "sub_out", label="Sub out", origin=PortOrigin.RESOLVED, on_change=RELAY_HANDLER
            )
        )
    definition.force_validation()
    return CallbackGroup(graph, definition, input_node, output_node)


def add_card(group: CallbackGroup) -> CallbackGroup:
    """Place the card standing for the group's Subgraph."""
    from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY

    group.card = make_node(group.graph, CARD, node_data={"store": {SUBGRAPH_KEY: group.definition.key}})
    return group


def build_group(graph, key: str = "sg_cb") -> CallbackGroup:
    """The interior and its card."""
    return add_card(build_interior(graph, key))
