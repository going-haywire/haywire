"""A setting promoted to a pin on a Graph-node card survives the card's interface rebuilds."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.node.promotion import demote_setting, promote_setting
from haywire.core.types.enums import PortOrigin, PortType

from tests.conftest import make_node

if TYPE_CHECKING:
    from haywire.barn.builtin.nodes.graph_node import GraphNode

pytestmark = pytest.mark.integration

_CARD = "haywire-core:node:GraphNode"


@pytest.fixture
def group(graph_with_library_system: BaseGraph):
    """A Group card over a one-inlet interface, with ``props.comment`` promoted to an inlet."""
    from haybale_testing.types.test_types import TEST_FLOAT

    from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY
    from haywire.barn.builtin.nodes.subgraph_io import SubgraphInputNode

    graph = graph_with_library_system
    definition = graph.add_subgraph(SubgraphDefinition(key="sg", label="Group"))
    boundary = make_node(definition, SubgraphInputNode.class_identity.registry_key)
    with boundary.node.rejig():
        boundary.node.add(TEST_FLOAT.as_outlet("value", label="Value"))
    card = make_node(graph, _CARD, node_data={"store": {SUBGRAPH_KEY: "sg"}})
    node = cast("GraphNode", card.node)
    node.reconcile_interface()
    promote_setting(node, "props", "comment", PortType.INLET)
    port_id = node.props._settings_descriptors()["comment"].storage_key
    return graph, boundary, card, port_id


def test_a_promoted_pin_survives_an_interface_change(group) -> None:
    from haybale_testing.types.test_types import TEST_FLOAT

    _graph, boundary, card, port_id = group
    with boundary.node.rejig(include=[]):
        boundary.node.add(TEST_FLOAT.as_outlet("gain", label="Gain"))

    cast("GraphNode", card.node).reconcile_interface()

    port = card.node.ports.get(port_id)
    assert port is not None
    assert port.origin is PortOrigin.PROMOTED
    card.node.props.comment = "shared"
    assert port.get_value() == "shared"


def test_a_promoted_pin_survives_a_save_and_load(group) -> None:
    graph, _boundary, card, port_id = group

    reloaded = BaseGraph(filestem="reloaded", validation_scheduler=SyncScheduler())
    assert reloaded.load_from_dict(graph.to_dict(include_data=True)) is True

    restored = reloaded.get_node_wrapper(card.node_id)
    assert restored is not None
    assert port_id in restored.node.ports


def test_demoting_a_setting_whose_pin_is_gone_clears_the_promotion(group) -> None:
    _graph, _boundary, card, port_id = group
    with card.node.rejig(include=[port_id]):
        pass
    assert port_id in card.node.props._promoted_keys

    demote_setting(card.node, port_id)

    assert port_id not in card.node.props._promoted_keys
