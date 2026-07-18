"""Graph props block round-trip (ADR 0022, ticket 01).

Only locally-set values serialize; an opinion-less graph emits an empty
values block; a dict WITHOUT the block (pre-feature graph) loads clean.
"""

import pytest

from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
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


def _registry():
    """Build an isolated registry AND make it the ambient DI registry, since
    BaseGraph.__init__ requires get_settings_registry() to resolve."""
    from haywire.core.di.context import set_settings_registry

    registry = create_test_settings_registry()
    # See tests/core/test_settings/test_graph_settings.py::_make_bag for why
    # this explicit registration is needed (autouse _pending_global reset).
    registry.register_schema(NodeDefaultSkinSettings)
    set_settings_registry(registry)
    return registry


def _graph():
    return BaseGraph(graph_id="g", name="G", validation_scheduler=SyncScheduler())


def test_opinionless_graph_serializes_empty_props():
    _registry()
    data = _graph().to_dict()
    assert data["props"] == {"values": {}, "promoted": {}}


def test_local_opinion_round_trips():
    _registry()
    g1 = _graph()
    g1.props.default_skin = "skin-mine"
    data = g1.to_dict()
    assert data["props"]["values"] == {"default_skin": "skin-mine"}

    g2 = _graph()
    assert g2.load_from_dict(data) is True
    assert g2.props.default_skin == "skin-mine"
    assert g2.props.is_locally_set("default_skin")


def test_missing_props_block_loads_with_defaults():
    """Pre-feature graph JSON has no 'props' key — must load unchanged."""
    _registry()
    g1 = _graph()
    data = g1.to_dict()
    del data["props"]
    g2 = _graph()
    g2.props.default_skin = "stale-opinion"  # reused instance with stale state
    assert g2.load_from_dict(data) is True
    assert not g2.props.is_locally_set("default_skin")  # reset_all ran


def test_load_restores_props_into_live_bag():
    _registry()
    g1 = _graph()
    g1.props.default_skin = "skin-early"
    data = g1.to_dict()

    g2 = _graph()
    assert g2.load_from_dict(data) is True
    assert g2.props.default_skin == "skin-early"
    # The ordering guarantee (props before nodes) is exercised with real
    # nodes in the Task 5 integration tests.
