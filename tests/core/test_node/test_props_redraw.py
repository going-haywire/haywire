"""Props-change → node-card redraw (NodeProperties.REDRAW_FIELDS).

NodeWrapper subscribes to the appearance-affecting props fields after each
build and requests a debounced redraw on change. Layout fields stay on the
NODE_MOVED path; graph-load restores never fire redraws.
"""

import importlib
from typing import List

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.types import ChangeReason, ValidationResult
from haywire.barn.builtin.types import FILL
from haywire.core.node.properties import NodeProperties


def _add_node(graph_obj: BaseGraph):
    from haybale_testing.nodes.testbed.print_node import TestPrintNode

    return graph_obj.create_node_wrapper(TestPrintNode.class_identity.registry_key, position=(100, 100))


def _redraw_results(results: List[ValidationResult], node_id: str) -> List[ValidationResult]:
    """Results in which *node_id* was marked with NODE_REDRAW_REQUESTED."""
    return [r for r in results if r.nodes.get(node_id) == ChangeReason.NODE_REDRAW_REQUESTED]


class TestRedrawFieldsSchema:
    """Pure schema contract — no graph or library system needed."""

    def test_redraw_fields_are_exactly_the_non_layout_props(self):
        fields = NodeProperties._property_settings()
        non_layout = {name for name, desc in fields.items() if desc._category != "layout"}
        assert set(NodeProperties.REDRAW_FIELDS) == non_layout

    def test_muted_description_does_not_promise_execution_skipping(self):
        desc = NodeProperties._property_settings()["muted"]
        assert "not yet implemented" in (desc._description or "")


@pytest.mark.integration
class TestPropsChangeTriggersRedraw:
    def test_visual_prop_change_requests_redraw(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)

        results: List[ValidationResult] = []
        graph_obj.subscribe_to_validation(results.append)

        wrapper.node.props.collapsed = True

        assert _redraw_results(results, wrapper.node_id), (
            "changing a REDRAW_FIELDS prop must mark the node NODE_REDRAW_REQUESTED"
        )

    def test_every_redraw_field_fires(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)
        values = {
            "muted": True,
            "collapsed": True,
            "condensed": True,
            "pinned": True,
            "skin": "some:skin:key",
            "layout_direction": "t2b",
            "body_fill": FILL.from_css_color("#ff0000"),
            "border_color": "#00ff0080",
            "border_thickness": 5,
            "border_roundness": 8,
            "comment": "hello",
            "show_comment": True,
        }
        assert set(values) == set(NodeProperties.REDRAW_FIELDS)

        for field_name, value in values.items():
            results: List[ValidationResult] = []
            graph_obj.subscribe_to_validation(results.append)
            setattr(wrapper.node.props, field_name, value)
            graph_obj.unsubscribe_from_validation(results.append)
            assert _redraw_results(results, wrapper.node_id), f"no redraw for '{field_name}'"

    def test_layout_prop_change_does_not_redraw(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)

        results: List[ValidationResult] = []
        graph_obj.subscribe_to_validation(results.append)

        wrapper.node.props.posX = 500.0
        wrapper.node.props.width = 240.0

        assert not _redraw_results(results, wrapper.node_id), (
            "layout props ride the NODE_MOVED path and must not full-redraw"
        )

    def test_graph_load_does_not_fire_redraws(self, graph_with_library_system, library_system):
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)
        wrapper.node.props.collapsed = True
        wrapper.node.props.body_fill = FILL.from_css_color("#00ff00")
        data = graph_obj.to_dict()

        from haywire.core.graph.scheduler import SyncScheduler

        g2 = BaseGraph(filestem="G2", validation_scheduler=SyncScheduler())
        results: List[ValidationResult] = []
        g2.subscribe_to_validation(results.append)
        assert g2.load_from_dict(data) is True

        loaded_id = next(iter(g2.node_wrappers))
        assert g2.node_wrappers[loaded_id].node.props.collapsed is True
        assert not _redraw_results(results, loaded_id), "restoring props at load must not request redraws"

    def test_rebuild_does_not_duplicate_subscription(self, graph_with_library_system):
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)

        # Simulate a hot-reload style rebuild: fresh instance, fresh bags.
        wrapper.build(wrapper.node._to_dict())

        results: List[ValidationResult] = []
        graph_obj.subscribe_to_validation(results.append)
        wrapper.node.props.condensed = True

        assert len(_redraw_results(results, wrapper.node_id)) == 1, (
            "one props change after a rebuild must produce exactly one redraw mark"
        )

    def test_resubscribe_on_same_instance_is_idempotent(self, graph_with_library_system):
        """An import-error rebuild keeps the old instance (build's _instantiate
        bails before swapping it), so _subscribe_props_redraw can run twice
        against the same bag. The bound-method callback must dedup."""
        graph_obj = graph_with_library_system
        wrapper = _add_node(graph_obj)

        wrapper._subscribe_props_redraw()  # second attach on the SAME instance

        results: List[ValidationResult] = []
        graph_obj.subscribe_to_validation(results.append)
        wrapper.node.props.muted = True

        assert len(_redraw_results(results, wrapper.node_id)) == 1, (
            "duplicate subscription would produce two redraw marks for one change"
        )

    def test_failed_build_still_subscribes(self, graph_with_library_system, monkeypatch):
        graph_obj = graph_with_library_system
        print_node_mod = importlib.import_module("haybale_testing.nodes.testbed.print_node")
        monkeypatch.setattr(
            print_node_mod.TestPrintNode, "on_testrun", lambda self: (False, "forced test failure")
        )

        wrapper = _add_node(graph_obj)
        assert wrapper.state.has_test_passed is False

        results: List[ValidationResult] = []
        graph_obj.subscribe_to_validation(results.append)
        wrapper.node.props.body_fill = FILL.from_css_color("#0000ff")

        assert _redraw_results(results, wrapper.node_id), (
            "a failed-build node's props edits must still refresh its (error) card"
        )
