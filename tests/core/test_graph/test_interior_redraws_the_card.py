"""A Graph-node card redraws when its interior changes visually, and never for a value edit.

The Inset draws the interior's stage inside the card, so a move or a stage
change inside must reach the card. A value edit must not: it would rebuild the
card, and with it a slider the user is still dragging.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.graph.types import ValidationResult
from haywire.core.node.node_wrapper import NodeWrapper

from tests.conftest import make_node

if TYPE_CHECKING:
    from haywire.barn.builtin.nodes.graph_node import GraphNode

pytestmark = [pytest.mark.integration]

_ADD_FLOAT = "haybale-testing:node:TestAddFloatNode"
_CARD = "haywire-core:node:GraphNode"


@pytest.fixture
def group(graph_with_library_system: BaseGraph):
    """A synchronous host graph with a Group card over one interior node, settled."""
    from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY

    graph = graph_with_library_system
    definition = graph.add_subgraph(SubgraphDefinition(key="sg", label="Group"))
    interior = make_node(definition, _ADD_FLOAT)
    card = make_node(graph, _CARD, node_data={"store": {SUBGRAPH_KEY: "sg"}})
    cast("GraphNode", card.node).reconcile_interface()
    graph.force_validation()
    seen: list[ValidationResult] = []
    graph.subscribe_to_validation(seen.append)
    return definition, card, interior, seen


def _card_redraws(seen: list[ValidationResult], card: NodeWrapper) -> bool:
    return any(card.node_id in r.nodes and r.nodes[card.node_id].requires_redraw() for r in seen)


def test_an_interior_move_redraws_the_card(group) -> None:
    definition, card, interior, seen = group

    definition.move_node(interior.node_id, 10.0, 20.0)

    assert _card_redraws(seen, card)


def test_an_interior_stage_change_redraws_the_card(group) -> None:
    _definition, card, interior, seen = group

    interior.node.props.on_stage = True

    assert _card_redraws(seen, card)


def test_an_interior_redraw_request_redraws_the_card(group) -> None:
    _definition, card, interior, seen = group

    interior.redraw()

    assert _card_redraws(seen, card)


def test_an_interior_value_edit_does_not_redraw_the_card(group) -> None:
    _definition, card, interior, seen = group

    interior.mark_value_edited()

    assert not _card_redraws(seen, card)
