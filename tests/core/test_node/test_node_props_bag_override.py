"""A node may override a framework prop's default by subclassing its ``props`` bag.

The bag is redeclared as a subclass of the inherited one, so every field it does
not redeclare is inherited. Replacing a ``graph()`` mirror with a plain
``setting`` detaches that ONE field from the graph tier — which is what a node
whose skin is a constraint rather than a preference wants (``RerouteNode``).
"""

from typing import cast

import pytest

from haywire.barn.builtin.types import CHOICES
from haywire.core.node import BaseNode, node
from haywire.core.settings import Settings, setting

REROUTE_SKIN = "haywire-core:skin:RerouteSkin"


def _reroute(graph_obj):
    from haywire.barn.builtin.nodes.reroute import RerouteNode

    return graph_obj.create_node_wrapper(RerouteNode.class_identity.registry_key, position=(0, 0))


def test_overriding_bag_is_a_distinct_class_that_inherits_the_rest():
    from haywire.barn.builtin.nodes.reroute import RerouteNode
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    # _settings_bags is typed dict[str, type]; cast to the bag base so the
    # Settings classmethods below are visible to mypy.
    reroute_bag = cast(type[Settings], RerouteNode._settings_bags["props"])
    base_bag = cast(type[Settings], TestPrintNode._settings_bags["props"])

    assert reroute_bag is not base_bag
    assert issubclass(reroute_bag, base_bag)
    # Overriding one field must not drop the other 13.
    assert set(reroute_bag._property_settings()) == set(base_bag._property_settings())


def test_a_non_subclass_bag_is_still_rejected():
    """The guard only permits a redeclaration that EXTENDS the inherited bag."""
    from haywire.core.settings import NodeSettings

    with pytest.raises(ValueError, match="without subclassing it"):

        @node(label="BadBagNode")
        class _BadBagNode(BaseNode):
            class props(NodeSettings):  # not a subclass of BaseNode.props
                skin = setting[CHOICES]("x")

            def init(self):
                pass

            def worker(self, context):
                return None


@pytest.mark.integration
class TestRerouteSkinIsPinned:
    def test_default_is_the_reroute_skin(self, graph_with_library_system):
        assert _reroute(graph_with_library_system).node.props.skin == REROUTE_SKIN

    def test_graph_default_does_not_reach_a_reroute(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        wrapper = _reroute(graph_obj)
        graph_obj.props.default_skin = "skin-graph"
        assert wrapper.node.props.skin == REROUTE_SKIN

    def test_reset_returns_to_the_reroute_skin_not_the_graph(self, graph_with_library_system):
        """The point of the override: reset lands on the node's own default."""
        graph_obj = graph_with_library_system
        wrapper = _reroute(graph_obj)
        graph_obj.props.default_skin = "skin-graph"

        wrapper.node.props.skin = "user-picked"
        assert wrapper.node.props.skin == "user-picked"

        wrapper.node.props.reset("skin")
        assert wrapper.node.props.skin == REROUTE_SKIN

    def test_other_nodes_still_track_the_graph_tier(self, graph_with_library_system):
        """The override is scoped to the node that declares it."""
        from haybale_testing.nodes.testbed.print_node import TestPrintNode

        graph_obj = graph_with_library_system
        _reroute(graph_obj)
        other = graph_obj.create_node_wrapper(TestPrintNode.class_identity.registry_key, position=(50, 0))
        graph_obj.props.default_skin = "skin-graph"
        assert other.node.props.skin == "skin-graph"

    def test_inherited_graph_mirrors_still_track(self, graph_with_library_system):
        """Only ``skin`` is detached; ``collapsed`` still mirrors the graph."""
        graph_obj = graph_with_library_system
        wrapper = _reroute(graph_obj)
        graph_obj.props.collapsed = True
        assert wrapper.node.props.collapsed is True

    def test_pinned_skin_does_not_serialize(self, graph_with_library_system):
        """A declared default is not a local override, so it stays out of the file."""
        wrapper = _reroute(graph_with_library_system)
        assert wrapper.node.props.to_dict()["values"] == {}
