"""A widget on a PROMOTED port writes through the setting, not into the cell.

A promoted port and its setting are one cell, two views — so a widget bound to
the port could change the value while the bag never learns anybody had an
opinion. Two things read that opinion (``_set_keys``):

* ``_to_dict()`` serializes a field only when it is set, so the edit is **lost
  on save**;
* the Reset menu item is enabled only when it is set, so the row offers **no way
  back**.

Reachable in two clicks — promote to outlet, turn the pin's widget on (an
outlet's ``ShowWidgetStrategy`` defaults to NEVER, which is why it stayed
hidden), type a value. The fix redirects the widget's WRITE through the
descriptor, exactly as the Properties panel already does; reads still come
straight off the shared cell.

Resolved once at widget-build time rather than checked inside
``DataPort.set_value``, which every edge-driven write crosses every frame.
"""

from typing import Any

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.node.promotion import promote_setting
from haywire.core.types.enums import PortType
from haywire.ui.panel.setting_widget_model import SettingWidgetModel
from haywire.ui.widget.factory import _widget_model_for

SETTINGS_NODE = "haybale-testing:node:SettingsNode"


def _promoted(graph: BaseGraph, field: str, direction: PortType) -> tuple[Any, Any]:
    """A SettingsNode with ``example.<field>`` promoted; returns (node, port)."""
    wrapper = graph.create_node_wrapper(SETTINGS_NODE, position=(0, 0))
    assert wrapper is not None
    node: Any = wrapper.node
    promote_setting(node, "example", field, direction=direction)
    descriptor = type(node.example).__dict__[field]
    return node, node.ports[descriptor.storage_key]


@pytest.mark.integration
class TestPromotedPortWritesThroughTheSetting:
    def test_the_model_is_the_panel_s_own(self, graph_with_library_system: BaseGraph):
        # Not a lookalike: the card and the panel share ONE write policy.
        _node, port = _promoted(graph_with_library_system, "example_float", PortType.OUTLET)
        assert isinstance(_widget_model_for(port), SettingWidgetModel)

    def test_an_unpromoted_port_still_binds_the_port_itself(self, graph_with_library_system: BaseGraph):
        wrapper = graph_with_library_system.create_node_wrapper(SETTINGS_NODE, position=(0, 0))
        assert wrapper is not None
        port = wrapper.node.ports["settings"]
        assert _widget_model_for(port) is port

    def test_a_card_edit_marks_the_opinion(self, graph_with_library_system: BaseGraph):
        node, port = _promoted(graph_with_library_system, "example_float", PortType.OUTLET)
        assert node.example._is_locally_set("example_float") is False

        _widget_model_for(port).set_value(0.25)

        assert node.example.example_float == 0.25
        assert node.example._is_locally_set("example_float") is True

    def test_a_card_edit_survives_a_save(self, graph_with_library_system: BaseGraph):
        # The defect that mattered most: the value changed on screen and was
        # silently absent from the saved graph.
        node, port = _promoted(graph_with_library_system, "example_float", PortType.OUTLET)
        _widget_model_for(port).set_value(0.25)
        assert node.example._to_dict()["values"] == {"example_float": 0.25}

    def test_promotion_alone_marks_nothing(self, graph_with_library_system: BaseGraph):
        # Promotion is structural; having an opinion is a value fact. An
        # untouched promoted field must still serialize as untouched.
        node, _port = _promoted(graph_with_library_system, "example_float", PortType.OUTLET)
        assert node.example._to_dict()["values"] == {}

    def test_an_edge_driven_write_marks_nothing(self, graph_with_library_system: BaseGraph):
        # Edge writes go to the PORT, never through the widget model, so a
        # graph-driven inlet stays clean and reset() keeps its meaning.
        node, port = _promoted(graph_with_library_system, "example_float", PortType.INLET)
        node.example._set_keys.discard(
            type(node.example).__dict__["example_float"].storage_key
        )  # undo promote-time marking, which INLET does deliberately
        port.set_value(0.75, edge_id="e1")
        assert node.example._is_locally_set("example_float") is False


@pytest.mark.integration
class TestOptionalStaysClearable:
    """The reported trap: an optional promoted to an outlet, edited on the card,
    with no route back to absence."""

    def test_a_card_edit_leaves_reset_available(self, graph_with_library_system: BaseGraph):
        node, port = _promoted(graph_with_library_system, "optional_int", PortType.OUTLET)
        assert node.example.optional_int is None

        _widget_model_for(port).set_value(42)

        assert node.example.optional_int == 42
        # Reset's enablement is exactly this predicate — previously False here.
        assert node.example._is_locally_set("optional_int") is True

    def test_reset_returns_an_absent_default_field_to_absence(self, graph_with_library_system: BaseGraph):
        node, port = _promoted(graph_with_library_system, "optional_int", PortType.OUTLET)
        _widget_model_for(port).set_value(42)
        node.example._reset("optional_int")
        assert node.example.optional_int is None

    def test_the_validator_still_applies_to_a_card_edit(self, graph_with_library_system: BaseGraph):
        # Routing through the descriptor means the card gets validation too —
        # writing the cell directly would have bypassed it.
        node, port = _promoted(graph_with_library_system, "optional_float", PortType.OUTLET)
        _widget_model_for(port).set_value(5.0)  # outside 0.0..1.0
        assert node.example.optional_float is None
