"""Graph mirror: node field declared graph(src=<GraphSettings field>).

Unit seam: public Settings/Graph API only. The node side is a minimal stub
exposing exactly the path the wiring walks (node.wrapper.graph) — no
library system needed.
"""

from typing import Any, cast

import pytest

from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.properties import GraphProperties
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.settings import NodeSettings, graph
from haywire.core.settings.descriptor import shadow
from haywire.core.skin.settings import NodeDefaultSkinSettings

pytestmark = [pytest.mark.unit, pytest.mark.core]

SKIN_KEY = "ui.node.default.skin.studio_skin"


@pytest.fixture(autouse=True)
def _isolate_di_settings_registry():
    """BaseGraph.__init__ requires the DI context's settings registry to be
    configured (get_settings_registry(), no constructor override — matches
    NodeData.__init__). Snapshot/restore the module-global slot around each
    test so set_settings_registry() here doesn't leak into other test files."""
    from haywire.core.di import context as di_context

    saved = di_context._settings_registry
    try:
        yield
    finally:
        di_context._settings_registry = saved


class ChainedBag(NodeSettings):
    """A node bag whose field graph-mirrors the graph bag's default_skin."""

    skin = graph(src=GraphProperties.default_skin)


class _StubWrapper:
    def __init__(self, graph_obj):
        self.graph = graph_obj


class _StubNode:
    """Exposes exactly what Settings._owning_graph() walks."""

    def __init__(self, graph_obj):
        self.wrapper = _StubWrapper(graph_obj)


def _registry():
    registry = create_test_settings_registry()
    registry.register_schema(NodeDefaultSkinSettings)
    return registry


def _make_chain():
    """Build a graph-attached chain. BaseGraph requires the DI context's
    registry (no constructor override), so set_settings_registry() runs
    before construction."""
    from haywire.core.di.context import set_settings_registry

    registry = _registry()
    set_settings_registry(registry)
    graph_obj = BaseGraph(filestem="G", validation_scheduler=SyncScheduler())
    bag = ChainedBag(registry=registry, node=cast(Any, _StubNode)(graph_obj))
    bag._subscribe_settings()
    return registry, graph_obj, bag


def test_unset_tracks_graph_value_live():
    registry, graph_obj, bag = _make_chain()
    graph_obj.props.default_skin = "skin-graph"
    assert bag.skin == "skin-graph"
    graph_obj.props.default_skin = "skin-graph-2"
    assert bag.skin == "skin-graph-2"


def test_subscribe_field_fires_on_graph_change():
    registry, graph_obj, bag = _make_chain()
    seen: list = []
    bag.subscribe_field("skin", lambda value, old: seen.append(value))
    graph_obj.props.default_skin = "skin-x"
    assert seen == ["skin-x"]


def test_local_set_wins_and_reset_returns_to_graph_current():
    registry, graph_obj, bag = _make_chain()
    graph_obj.props.default_skin = "skin-graph"
    bag.skin = "skin-node"
    assert bag.skin == "skin-node"
    graph_obj.props.default_skin = "skin-graph-2"
    assert bag.skin == "skin-node"  # set ignores
    bag.reset("skin")
    assert bag.skin == "skin-graph-2"  # falls to graph CURRENT, not framework
    graph_obj.props.default_skin = "skin-graph-3"
    assert bag.skin == "skin-graph-3"  # tracking resumed


def test_transitive_chain_framework_to_node():
    registry, graph_obj, bag = _make_chain()
    registry.set_global(SKIN_KEY, "skin-fw")
    assert graph_obj.props.default_skin == "skin-fw"
    assert bag.skin == "skin-fw"  # framework → graph → node
    graph_obj.props.default_skin = "skin-graph"  # graph opinion interposes
    registry.set_global(SKIN_KEY, "skin-fw-2")
    assert bag.skin == "skin-graph"  # blocked at the graph tier
    graph_obj.props.reset("default_skin")
    assert bag.skin == "skin-fw-2"  # chain reopens end to end


def test_detached_bag_holds_descriptor_default():
    """No node / no graph → descriptor default, NOT live.

    Deliberate contract: no production path constructs a detached bag (a
    NodeWrapper's graph is a non-optional constructor arg); an honest
    default surfaces the detachment instead of masking it."""
    registry = _registry()
    registry.set_global(SKIN_KEY, "skin-fw")
    bag = ChainedBag(registry=registry, node=cast(Any, None))
    bag._subscribe_settings()
    assert bag.skin is None  # descriptor default, not "skin-fw"
    registry.set_global(SKIN_KEY, "skin-fw-2")
    assert bag.skin is None  # and not tracking either
    bag.skin = "skin-local"  # local writes still work
    assert bag.skin == "skin-local"


def test_plain_shadow_of_graph_field_fails_loudly():
    class Misdeclared(NodeSettings):
        skin = shadow(src=GraphProperties.default_skin)  # should be graph(...)

    bag = Misdeclared(registry=_registry(), node=None)
    with pytest.raises(TypeError, match=r"graph\("):
        bag._subscribe_settings()


def test_cleanup_detaches_graph_cell_adapter():
    registry, graph_obj, bag = _make_chain()
    graph_obj.props.default_skin = "skin-a"
    bag.cleanup()
    graph_obj.props.default_skin = "skin-b"
    desc = type(bag)._property_settings()["skin"]
    assert bag._cell_for(desc).get_value() == "skin-a"  # no sync after cleanup


def test_node_removal_does_not_leak_callbacks():
    registry, graph_obj, bag = _make_chain()
    seen: list = []
    bag.subscribe_field("skin", lambda value, old: seen.append(value))
    bag.cleanup()
    graph_obj.props.default_skin = "skin-after"
    assert seen == []
