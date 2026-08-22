"""GraphSettings flavour + GraphProperties bag + graph() factory.

The graph→framework hop is the EXISTING registry-key mirror; these tests
prove it works on a graph-owned bag (unset tracks, set wins, reset resumes)
and that the graph() declaration API validates eagerly.
"""

import pytest

from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.graph.properties import GraphProperties
from haywire.core.settings import GraphSettings, NodeSettings, graph
from haywire.core.skin.settings import NodeDefaultSkinSettings

pytestmark = [pytest.mark.unit, pytest.mark.core]

SKIN_KEY = "ui.node.default.skin.studio_skin"


@pytest.fixture(autouse=True)
def _isolate_di_settings_registry():
    """BaseGraph.__init__ requires the DI context's settings registry to be
    configured (get_settings_registry(), no constructor override — matches
    NodeData.__init__). Snapshot/restore the module-global slot around each
    test so a set_settings_registry() call here doesn't leak into other
    test files in the same process."""
    from haywire.core.di import context as di_context

    saved = di_context._settings_registry
    try:
        yield
    finally:
        di_context._settings_registry = saved


def _make_bag():
    registry = create_test_settings_registry()
    # register_schema is idempotent, so registering explicitly here is safe
    # even if NodeDefaultSkinSettings self-registered elsewhere.
    registry.register_schema(NodeDefaultSkinSettings)
    bag = GraphProperties(registry=registry, graph=None)
    bag._subscribe_settings()
    return registry, bag


def test_flavour_shape():
    registry, bag = _make_bag()
    assert isinstance(bag, GraphSettings)
    assert bag._node is None  # promotion guard keys on this
    assert bag._graph is None  # standalone bag; BaseGraph sets it (Task 2)


def test_owner_cls_recorded_by_set_name():
    assert GraphProperties.default_skin._owner_cls is GraphProperties
    assert NodeDefaultSkinSettings.studio_skin._owner_cls is NodeDefaultSkinSettings


def test_graph_factory_sets_flag():
    class NB(NodeSettings):
        f = graph(src=GraphProperties.default_skin)

    assert NB.f.is_graph_mirror is True
    # The graph bag's own field is a plain registry-key mirror, NOT a graph mirror.
    assert GraphProperties.default_skin.is_graph_mirror is False
    assert GraphProperties.default_skin.is_mirror is True


def test_graph_factory_rejects_non_graphsettings_src():
    with pytest.raises(TypeError, match="GraphSettings"):
        graph(src=NodeDefaultSkinSettings.studio_skin)  # a FrameworkSettings field


def test_unset_tracks_framework_value():
    registry, bag = _make_bag()
    registry.set_global(SKIN_KEY, "skin-A")
    assert bag.default_skin == "skin-A"
    registry.set_global(SKIN_KEY, "skin-B")
    assert bag.default_skin == "skin-B"


def test_local_set_wins_and_reset_resumes_tracking():
    registry, bag = _make_bag()
    registry.set_global(SKIN_KEY, "skin-A")
    bag.default_skin = "skin-local"
    assert bag.default_skin == "skin-local"
    assert bag.is_locally_set("default_skin")
    registry.set_global(SKIN_KEY, "skin-C")
    assert bag.default_skin == "skin-local"  # set ignores
    bag.reset("default_skin")
    assert bag.default_skin == "skin-C"  # back on the chain
    registry.set_global(SKIN_KEY, "skin-D")
    assert bag.default_skin == "skin-D"  # tracking resumed


def test_subscribe_fires_on_framework_change():
    registry, bag = _make_bag()
    seen: list[tuple] = []
    bag.subscribe(lambda name, value, old: seen.append((name, value)))
    registry.set_global(SKIN_KEY, "skin-E")
    assert ("default_skin", "skin-E") in seen


def test_promotion_unavailable():
    registry, bag = _make_bag()
    from haywire.core.types.enums import PortType

    with pytest.raises(ValueError, match="bag has no bound node"):
        bag.promote("default_skin", PortType.INLET)


def test_cleanup_detaches_registry_subscription():
    registry, bag = _make_bag()
    registry.set_global(SKIN_KEY, "skin-A")
    bag.cleanup()
    registry.set_global(SKIN_KEY, "skin-Z")
    # The dead bag must not have been re-synced (cell untouched after cleanup).
    desc = type(bag)._property_settings()["default_skin"]
    assert bag._cell_for(desc).get_value() == "skin-A"


def _make_registry():
    """Build an isolated registry AND make it the ambient DI registry, since
    BaseGraph.__init__ requires get_settings_registry() to resolve (no
    constructor override — see _isolate_di_settings_registry above)."""
    from haywire.core.di.context import set_settings_registry

    registry = create_test_settings_registry()
    registry.register_schema(NodeDefaultSkinSettings)
    set_settings_registry(registry)
    return registry


def test_base_graph_wires_props_bag_from_di():
    """BaseGraph requires the DI context's registry (same precondition as
    NodeData) and wires graph.props to it — no constructor override."""
    from haywire.core.graph.base import BaseGraph

    _make_registry()
    graph_obj = BaseGraph(filestem="G")
    assert isinstance(graph_obj.props, GraphProperties)
    assert graph_obj.props._graph is graph_obj


def test_base_graph_uses_the_ambient_di_registry():
    from haywire.core.graph.base import BaseGraph

    registry = _make_registry()
    graph_obj = BaseGraph(filestem="G")
    registry.set_global(SKIN_KEY, "skin-A")
    assert graph_obj.props.default_skin == "skin-A"


def test_settings_bag_for_is_the_lookup_seam():
    from haywire.core.graph.base import BaseGraph

    _make_registry()
    graph_obj = BaseGraph(filestem="G")
    assert graph_obj.settings_bag_for(GraphProperties) is graph_obj.props
    assert graph_obj.settings_bag_for(GraphSettings) is graph_obj.props  # isinstance match

    class UnrelatedBag(GraphSettings):
        pass

    assert graph_obj.settings_bag_for(UnrelatedBag) is None


def test_graph_cleanup_releases_bag():
    from haywire.core.graph.base import BaseGraph

    registry = _make_registry()
    graph_obj = BaseGraph(filestem="G")
    registry.set_global(SKIN_KEY, "skin-A")
    graph_obj.cleanup()
    registry.set_global(SKIN_KEY, "skin-Z")
    desc = type(graph_obj.props)._property_settings()["default_skin"]
    assert graph_obj.props._cell_for(desc).get_value() == "skin-A"


def test_graph_bag_never_carries_a_node():
    """The setting-row menu's promote guard keys on obj._node is None
    (_build_row_menu in render_utils). This invariant is what keeps promote
    entries structurally absent for every GraphSettings bag."""
    registry, bag = _make_bag()
    assert bag._node is None
    from haywire.core.graph.base import BaseGraph

    _make_registry()
    graph_obj = BaseGraph(filestem="G")
    assert graph_obj.props._node is None
