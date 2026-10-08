"""The inspector names a swinglet's direction `swinglet`, not `inlet`."""

import pytest

from haywire.core.node.inspector import NodeInstanceInspector

from tests.conftest import make_node


@pytest.mark.integration
@pytest.mark.core
def test_a_swinglet_reports_its_own_direction(graph_with_library_system):
    from haybale_testing.nodes.testbed.swinglet_probe import SwingletPassProbeNode

    node = make_node(graph_with_library_system, SwingletPassProbeNode.class_identity.registry_key).node

    assert {p.id: p.direction for p in NodeInstanceInspector(node).ports()} == {"s": "swinglet"}
