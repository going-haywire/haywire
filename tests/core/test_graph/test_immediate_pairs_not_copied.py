"""An immediate value crosses by the relay alone; execution copies deferred values only."""

import pytest

from tests.core.test_graph.callback_group import add_card, build_interior

pytestmark = pytest.mark.integration


def test_no_boundary_or_card_pairs_an_immediate_port(graph_with_library_system):
    from haywire.barn.builtin.types import FLOAT
    from haywire.core.types.enums import PortOrigin

    group = build_interior(graph_with_library_system)
    # Flags only the new id, so the stamped callback port stays.
    with group.input_node.node.rejig(include=["gain"]):
        group.input_node.node.add(FLOAT.as_outlet("gain", origin=PortOrigin.RESOLVED))
    add_card(group)

    for node in (group.input_node.node, group.output_node.node, group.card.node):
        assert node.on_assembly() == (True, None)

    pairs = [
        *group.input_node.node.cache.pairs,
        *group.output_node.node.cache.pairs,
        *group.card.node.cache.inward,
    ]
    assert any(pair[1].id == "gain" for pair in group.input_node.node.cache.pairs)
    assert not any(port.is_immediate for pair in pairs for port in pair)
