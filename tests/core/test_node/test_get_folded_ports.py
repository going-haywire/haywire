"""NodeData.get_folded_ports — the port list a FOLDED node card draws.

Pulled out of the deleted NodeVisibility.ports() (see ADR 0032's "Superseded"
section, 2026-09): the fold-vs-unfold branch always happens once, in the
skin's top-level render(), so by the time a skin needs a port list it already
knows which of get_visible_ports()/get_folded_ports() it wants — there was
never a real caller asking for both through one object.
"""

from typing import Any, List, cast

import pytest

from haywire.core.node.data import NodeData

pytestmark = pytest.mark.unit


class _FakePort:
    def __init__(self, pid, *, order=0, linked=False, section=None, is_group=False, visible=True):
        self.id = pid
        self.order = order
        self.section = section
        self.is_group = is_group
        self._linked = linked
        self._visible = visible

    def is_linked(self):
        return self._linked


class _FakeNode:
    """Stands in for NodeData's port accessors — get_folded_ports is defined
    in terms of get_all_ports, so faking that one is enough."""

    def __init__(self, ports):
        self._ports = ports

    def get_all_ports(self):
        return sorted(self._ports, key=lambda p: p.order)


def _fake_node(ports: List[Any]):
    return cast(Any, _FakeNode(ports))


def _get_folded_ports(node) -> List[Any]:
    """Call the real, unbound method against the fake — get_folded_ports has
    no dependency on anything else NodeData carries."""
    return NodeData.get_folded_ports(node)


class TestGetFoldedPorts:
    def test_keeps_every_linked_port(self):
        linked = _FakePort("linked", order=1, linked=True)
        loose = _FakePort("loose", order=2, linked=False)
        node = _fake_node([linked, loose])

        assert _get_folded_ports(node) == [linked]

    def test_ignores_group_collapse(self):
        """An edge must always find its endpoint: a linked port hidden by a
        collapsed GROUP still gets a pin on a folded card, because a folded
        card is all header and there is nowhere else for it to go."""
        buried = _FakePort("buried", order=1, linked=True, visible=False)
        node = _fake_node([buried])

        assert _get_folded_ports(node) == [buried]

    def test_drops_sections_and_group_controls(self):
        """Matches get_hidden_connected_ports' filter. A group control port is
        never linked anyway, so it falls out twice over."""
        section = _FakePort("sect", order=1, linked=True, section="advanced")
        group = _FakePort("grp", order=2, linked=True, is_group=True)
        real = _FakePort("real", order=3, linked=True)
        node = _fake_node([section, group, real])

        assert _get_folded_ports(node) == [real]

    def test_preserves_display_order(self):
        late = _FakePort("late", order=9, linked=True)
        early = _FakePort("early", order=1, linked=True)
        node = _fake_node([late, early])

        assert _get_folded_ports(node) == [early, late]

    def test_drops_unlinked_ports(self):
        """The element-count win: a freshly added node has no edges, so
        folding it drops every pin."""
        loose = _FakePort("loose", order=1, linked=False)
        node = _fake_node([loose])

        assert _get_folded_ports(node) == []


@pytest.mark.integration
class TestAgainstRealNodeData:
    """The fakes above pin the filter; this pins that it fits reality — a
    NodeData port accessor that changes shape fails here rather than
    silently in a card."""

    def _add_node(self, graph_obj):
        from haybale_testing.nodes.testbed.print_node import TestPrintNode

        return graph_obj.create_node_wrapper(TestPrintNode.class_identity.registry_key, position=(100, 100))

    def test_runs_against_real_node_data(self, graph_with_library_system):
        wrapper = self._add_node(graph_with_library_system)
        node = wrapper.node

        folded = node.get_folded_ports()
        assert all(p.is_linked() for p in folded)
        assert len(folded) <= len(node.get_all_ports())

    def test_unlinked_node_folds_to_no_ports(self, graph_with_library_system):
        wrapper = self._add_node(graph_with_library_system)
        assert wrapper.node.get_folded_ports() == []
