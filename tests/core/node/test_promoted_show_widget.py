# tests/core/node/test_promoted_show_widget.py
"""
Per-instance widget visibility on a promoted port.

A promoted port's ``show_widget`` is user-settable (the pin menu), unlike an
author-declared port's, whose strategy stays the author's decision (ADR 0003).
The choice must reach BOTH the live port (what ``should_show_widget()`` reads)
and the bag's promotion record (what survives a save — a promoted port is
regenerated on load, never serialized).

Same fixtures as the sibling promotion files: "haybale-testing:node:SettingsNode",
bag accessor "example", field "example_float".
"""

import pytest

from haywire.core.node.promotion import (
    demote_setting,
    promote_setting,
    set_promoted_show_widget,
)
from haywire.core.types.enums import PortType, ShowWidgetStrategy, default_show_widget

pytestmark = pytest.mark.integration


def _pid(node) -> str:
    return type(node.example).__dict__["example_float"].storage_key


def _make(graph):
    return graph.create_node_wrapper("haybale-testing:node:SettingsNode", position=(0, 0)).node


class TestDirectionDefaults:
    def test_promoted_outlet_hides_its_widget_by_default(self, graph_with_library_system, library_system):
        node = _make(graph_with_library_system)
        promote_setting(node, "example", "example_float", PortType.OUTLET)
        port = node.ports[_pid(node)]
        assert port.show_widget is ShowWidgetStrategy.NEVER
        assert port.should_show_widget() is False

    def test_promoted_inlet_shows_its_widget_while_unlinked(self, graph_with_library_system, library_system):
        node = _make(graph_with_library_system)
        promote_setting(node, "example", "example_float", PortType.INLET)
        port = node.ports[_pid(node)]
        assert port.show_widget is ShowWidgetStrategy.NOT_LINKED
        assert port.should_show_widget() is True

    def test_default_helper_matches_what_the_factories_inject(
        self, graph_with_library_system, library_system
    ):
        """The helper is the single source of truth for the per-direction
        defaults; if it drifts from the as_* factories, saved graphs start
        omitting the wrong strategy."""
        for direction in (PortType.INLET, PortType.OUTLET, PortType.CONFIG):
            node = _make(graph_with_library_system)
            promote_setting(node, "example", "example_float", direction)
            assert node.ports[_pid(node)].show_widget is default_show_widget(direction)


class TestSetStrategy:
    def test_set_updates_the_live_port(self, graph_with_library_system, library_system):
        node = _make(graph_with_library_system)
        promote_setting(node, "example", "example_float", PortType.OUTLET)
        set_promoted_show_widget(node, _pid(node), ShowWidgetStrategy.ALWAYS)

        port = node.ports[_pid(node)]
        assert port.show_widget is ShowWidgetStrategy.ALWAYS
        assert port.should_show_widget() is True

    def test_set_records_the_choice_in_the_bag(self, graph_with_library_system, library_system):
        """Port-only would work until reload, then silently revert."""
        node = _make(graph_with_library_system)
        promote_setting(node, "example", "example_float", PortType.OUTLET)
        set_promoted_show_widget(node, _pid(node), ShowWidgetStrategy.ALWAYS)

        assert node.example.get_promoted_show_widget("example_float") is ShowWidgetStrategy.ALWAYS

    def test_set_on_an_unpromoted_port_is_a_noop(self, graph_with_library_system, library_system):
        """An author-declared port keeps ADR 0003's contract — this never
        touches one."""
        node = _make(graph_with_library_system)
        author_ports = [p for p in node.ports.values() if not p.promoted]
        assert author_ports, "fixture node must have at least one author-declared port"
        port = author_ports[0]
        before = port.show_widget

        set_promoted_show_widget(node, port.id, ShowWidgetStrategy.ALWAYS)
        assert port.show_widget is before

    def test_set_on_an_unknown_port_is_a_noop(self, graph_with_library_system, library_system):
        node = _make(graph_with_library_system)
        set_promoted_show_widget(node, "no-such-port", ShowWidgetStrategy.ALWAYS)


class TestRoundTrip:
    def test_choice_survives_a_full_round_trip(self, graph_with_library_system, library_system):
        graph = graph_with_library_system
        node = _make(graph)
        promote_setting(node, "example", "example_float", PortType.OUTLET)
        pid = _pid(node)
        set_promoted_show_widget(node, pid, ShowWidgetStrategy.ALWAYS)

        dumped = node._to_dict()
        assert dumped["settings"]["example"]["promoted"] == {
            pid: {"direction": "outlet", "show_widget": "always"}
        }

        fresh = _make(graph)
        fresh._initialize_from_dict(dumped)
        assert fresh.ports[pid].show_widget is ShowWidgetStrategy.ALWAYS
        assert fresh.ports[pid].should_show_widget() is True

    def test_untouched_promotion_round_trips_to_its_direction_default(
        self, graph_with_library_system, library_system
    ):
        graph = graph_with_library_system
        node = _make(graph)
        promote_setting(node, "example", "example_float", PortType.OUTLET)
        pid = _pid(node)

        dumped = node._to_dict()
        assert "show_widget" not in dumped["settings"]["example"]["promoted"][pid]

        fresh = _make(graph)
        fresh._initialize_from_dict(dumped)
        assert fresh.ports[pid].show_widget is ShowWidgetStrategy.NEVER

    def test_demote_discards_the_choice(self, graph_with_library_system, library_system):
        """The record IS the storage, so demoting drops it. Freeze-on-disconnect
        protects values, not view preferences — re-promoting starts from the
        direction default again."""
        node = _make(graph_with_library_system)
        promote_setting(node, "example", "example_float", PortType.OUTLET)
        pid = _pid(node)
        set_promoted_show_widget(node, pid, ShowWidgetStrategy.ALWAYS)

        demote_setting(node, pid)
        promote_setting(node, "example", "example_float", PortType.OUTLET)

        assert node.ports[pid].show_widget is ShowWidgetStrategy.NEVER
        assert node.example.get_promoted_show_widget("example_float") is None
