"""Edge defaults: a graph's computed edges take their head and width from framework < graph."""

import pytest

from haywire.barn.builtin.widget_keys import ARROW_HEAD_WIDGET
from haywire.core.di.context import get_settings_registry
from haywire.core.graph.base import BaseGraph

ARROW_KEY = "ui.edge.default.arrow"
WIDTH_KEY = "ui.edge.default.width"


@pytest.fixture(autouse=True)
def _clean_framework_tier(library_system):
    """The registry is process-shared: clear the framework tier around every test."""
    registry = get_settings_registry()
    for key in (ARROW_KEY, WIDTH_KEY):
        registry.reset_global(key)
    yield
    for key in (ARROW_KEY, WIDTH_KEY):
        registry.reset_global(key)


@pytest.mark.integration
class TestEdgeDefaults:
    def test_a_graph_starts_with_todays_look(self, graph_with_library_system):
        props = graph_with_library_system.props
        assert props.edge_arrow == "none"
        assert props.edge_width == 2.0

    def test_an_unset_graph_tracks_the_studio_value(self, graph_with_library_system):
        get_settings_registry().set_global(ARROW_KEY, "arrow")
        get_settings_registry().set_global(WIDTH_KEY, 3.0)

        assert graph_with_library_system.props.edge_arrow == "arrow"
        assert graph_with_library_system.props.edge_width == 3.0

    def test_a_graph_value_wins_and_reset_falls_back(self, graph_with_library_system):
        props = graph_with_library_system.props
        get_settings_registry().set_global(ARROW_KEY, "arrow")
        props.edge_arrow = "open"
        assert props.edge_arrow == "open"

        props._reset("edge_arrow")
        assert props.edge_arrow == "arrow"

    def test_a_graph_value_survives_save_and_load(self, graph_with_library_system):
        graph_with_library_system.props.edge_width = 3.5
        data = graph_with_library_system.to_dict()

        loaded = BaseGraph(filestem="G2")
        assert loaded.load_from_dict(data) is True
        assert loaded.props.edge_width == 3.5
        assert not loaded.props._is_locally_set("edge_arrow")

    def test_both_tiers_pick_the_head_with_the_arrow_head_widget(self, graph_with_library_system):
        from haywire.core.edge.settings import EdgeDefaultSettings

        graph_fields = type(graph_with_library_system.props)._settings_descriptors()
        assert graph_fields["edge_arrow"].widget_key == ARROW_HEAD_WIDGET
        assert EdgeDefaultSettings._settings_descriptors()["arrow"].widget_key == ARROW_HEAD_WIDGET


@pytest.mark.integration
def test_a_studio_write_notifies_a_subscriber_of_an_unset_graph(graph_with_library_system):
    """The canvas subscribes to the graph's field: a studio-tier write must reach it."""
    props = graph_with_library_system.props
    seen: list = []
    for field in ("edge_arrow", "edge_width"):
        props._subscribe_field(field, lambda value, old, field=field: seen.append((field, value)))

    get_settings_registry().set_global(ARROW_KEY, "arrow")
    get_settings_registry().set_global(WIDTH_KEY, 3.0)

    assert ("edge_arrow", "arrow") in seen
    assert ("edge_width", 3.0) in seen
