"""Every connection combination a promoted ``OPTIONAL[T]`` setting can be part of.

Two mechanisms are under test together, because neither is meaningful alone:

* **A wrapper field promotes to a port of its ELEMENT type.** An
  ``OPTIONAL[INT]`` setting becomes an ``INT`` pin, so it connects to whatever
  ``INT`` connects to — including through adapters. Without this the pin would
  be ``OPTIONAL[INT]``-typed and, since no ``OPTIONAL[T] -> T`` adapter exists,
  would silently refuse every edge.

* **Absence travels on the sink FIELD's capability, not on the declared type**
  (``DataField.accepts_absence``). Connectivity and absence-capability were only
  ever the same question by accident; separating them is what lets a promoted
  optional be honestly an ``INT`` pin *whose sink may have somewhere to put
  nothing*.

The matrix, all against real graph edges:

    source (promoted outlet)   sink                     present   absent
    ------------------------   ----------------------   -------   ----------------
    OPTIONAL[INT]              OPTIONAL[INT] (promoted) flows     ARRIVES as None
    OPTIONAL[INT]              INT           (promoted) flows     SKIPPED, last kept
    OPTIONAL[INT]              FLOAT (via adapter)      converts  SKIPPED, last kept
    INT                        OPTIONAL[INT] (promoted) flows     n/a

The "skipped" rows are not a nicety: ``INTField.set_value`` coerces with
``int(value)``, so forwarding ``None`` into a plain ``INT`` sink would raise
``TypeError`` from inside propagation — an exception nowhere near the user
action that caused it.

See ADR 0033.
"""

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.node.promotion import promote_setting
from haywire.core.types.enums import PortType

SETTINGS_NODE = "haybale-testing:node:SettingsNode"


def _storage_key(node, accessor: str, field: str) -> str:
    return type(getattr(node, accessor)).__dict__[field].storage_key


def _promote(node, field: str, direction: PortType) -> str:
    """Promote ``example.<field>`` and return the generated port id."""
    promote_setting(node, "example", field, direction=direction)
    return _storage_key(node, "example", field)


def _settings_node(graph: BaseGraph, x: float):
    wrapper = graph.create_node_wrapper(SETTINGS_NODE, position=(x, 0))
    assert wrapper is not None, "SettingsNode creation failed"
    return wrapper


def _drive(src_node, field: str, value, sink_port) -> None:
    """Write the source setting out of frame, then let the sink pull.

    A promoted outlet is always ``is_linked_lazy``: the write marks the sink
    dirty and the pull is deferred to the consumer's next execution, which
    ``resolve_dirty_data()`` stands in for here.
    """
    setattr(src_node.example, field, value)
    sink_port.resolve_dirty_data()


# ===========================================================================
# The port a wrapper field promotes to
# ===========================================================================


@pytest.mark.integration
class TestPromotedPortTyping:
    def test_the_pin_carries_the_element_type(self, graph_with_library_system: BaseGraph):
        node = _settings_node(graph_with_library_system, 0).node
        pid = _promote(node, "optional_int", PortType.OUTLET)

        from haywire.barn.builtin.types import INT, OPTIONAL

        port = node.ports[pid]
        assert port.type_cls is INT, "the pin must be an ordinary INT, not OPTIONAL[INT]"
        assert port.stored_type is INT, "what flows on the wire is the element type"
        # ...while the borrowed cell still knows what it really is, which is
        # what OptionalWidget reads to pick the inner widget.
        assert port.data.type_cls is OPTIONAL[INT]

    def test_the_borrowed_cell_accepts_absence(self, graph_with_library_system: BaseGraph):
        node = _settings_node(graph_with_library_system, 0).node
        opt = node.ports[_promote(node, "optional_int", PortType.INLET)]
        plain = node.ports[_promote(node, "example_int", PortType.INLET)]

        assert opt.data.accepts_absence() is True
        assert plain.data.accepts_absence() is False

    def test_a_plain_field_is_unaffected(self, graph_with_library_system: BaseGraph):
        node = _settings_node(graph_with_library_system, 0).node
        pid = _promote(node, "example_int", PortType.OUTLET)

        from haywire.barn.builtin.types import INT

        assert node.ports[pid].type_cls is INT
        assert node.ports[pid].data.type_cls is INT


# ===========================================================================
# OPTIONAL -> OPTIONAL : absence is real information and crosses the edge
# ===========================================================================


@pytest.mark.integration
class TestOptionalToOptional:
    def _wire(self, graph: BaseGraph):
        src_w, sink_w = _settings_node(graph, 0), _settings_node(graph, 300)
        src, sink = src_w.node, sink_w.node
        out_pid = _promote(src, "optional_int", PortType.OUTLET)
        in_pid = _promote(sink, "optional_int", PortType.INLET)
        edge = graph.create_edge_wrapper(src_w.node_id, out_pid, sink_w.node_id, in_pid)
        assert edge is not None, "OPTIONAL -> OPTIONAL produced no edge"
        assert edge.state.is_valid(), "OPTIONAL -> OPTIONAL must connect"
        return src, sink, sink.ports[in_pid]

    def test_the_edge_connects(self, graph_with_library_system: BaseGraph):
        self._wire(graph_with_library_system)

    def test_a_present_value_flows(self, graph_with_library_system: BaseGraph):
        src, sink, sink_port = self._wire(graph_with_library_system)
        _drive(src, "optional_int", 7, sink_port)
        assert sink.example.optional_int == 7

    def test_absence_arrives_as_absence(self, graph_with_library_system: BaseGraph):
        src, sink, sink_port = self._wire(graph_with_library_system)
        _drive(src, "optional_int", 7, sink_port)
        assert sink.example.optional_int == 7

        # The source now has nothing to say, and this sink can represent that.
        _drive(src, "optional_int", None, sink_port)
        assert sink.example.optional_int is None, "an optional sink must receive absence, not a stale 7"


# ===========================================================================
# OPTIONAL -> plain element : connects natively, absence is skipped
# ===========================================================================


@pytest.mark.integration
class TestOptionalToPlainElement:
    def _wire(self, graph: BaseGraph):
        src_w, sink_w = _settings_node(graph, 0), _settings_node(graph, 300)
        src, sink = src_w.node, sink_w.node
        out_pid = _promote(src, "optional_int", PortType.OUTLET)
        in_pid = _promote(sink, "example_int", PortType.INLET)
        edge = graph.create_edge_wrapper(src_w.node_id, out_pid, sink_w.node_id, in_pid)
        assert edge is not None, "no edge was produced"
        assert edge.state.is_valid(), (
            "an element-typed pin must connect to an ordinary INT inlet — this is "
            "the whole point of promoting to the element type"
        )
        return src, sink, sink.ports[in_pid]

    def test_the_edge_connects(self, graph_with_library_system: BaseGraph):
        self._wire(graph_with_library_system)

    def test_a_present_value_flows(self, graph_with_library_system: BaseGraph):
        src, sink, sink_port = self._wire(graph_with_library_system)
        _drive(src, "optional_int", 12, sink_port)
        assert sink.example.example_int == 12

    def test_absence_is_skipped_and_the_sink_keeps_its_last_value(
        self, graph_with_library_system: BaseGraph
    ):
        src, sink, sink_port = self._wire(graph_with_library_system)
        _drive(src, "optional_int", 12, sink_port)
        assert sink.example.example_int == 12

        # An INT cell has nowhere to put absence (int(None) raises), so the
        # source says nothing this frame rather than crashing propagation.
        _drive(src, "optional_int", None, sink_port)
        assert sink.example.example_int == 12

    def test_absence_does_not_raise_inside_propagation(self, graph_with_library_system: BaseGraph):
        # Explicit regression guard: forwarding None here would surface as a
        # TypeError from INTField.set_value, far from the user action.
        src, _sink, sink_port = self._wire(graph_with_library_system)
        _drive(src, "optional_int", None, sink_port)


# ===========================================================================
# OPTIONAL -> a DIFFERENT type : the element's own adapters apply
# ===========================================================================


@pytest.mark.integration
class TestOptionalThroughAnAdapter:
    def _wire(self, graph: BaseGraph):
        src_w, sink_w = _settings_node(graph, 0), _settings_node(graph, 300)
        src, sink = src_w.node, sink_w.node
        out_pid = _promote(src, "optional_int", PortType.OUTLET)
        in_pid = _promote(sink, "example_float", PortType.INLET)
        edge = graph.create_edge_wrapper(src_w.node_id, out_pid, sink_w.node_id, in_pid)
        assert edge is not None, "no edge was produced"
        assert edge.state.is_valid(), (
            "INT -> FLOAT is an ordinary adapter chain; the wrapper must not block it"
        )
        return src, sink, sink.ports[in_pid]

    def test_a_present_value_converts(self, graph_with_library_system: BaseGraph):
        src, sink, sink_port = self._wire(graph_with_library_system)
        _drive(src, "optional_int", 3, sink_port)
        assert sink.example.example_float == pytest.approx(3.0)

    def test_absence_is_skipped_not_converted(self, graph_with_library_system: BaseGraph):
        src, sink, sink_port = self._wire(graph_with_library_system)
        _drive(src, "optional_int", 3, sink_port)
        _drive(src, "optional_int", None, sink_port)
        # Absence has no representation to convert — the adapter never runs.
        assert sink.example.example_float == pytest.approx(3.0)


# ===========================================================================
# plain element -> OPTIONAL : an ordinary edge drives an optional field
# ===========================================================================


@pytest.mark.integration
class TestPlainElementToOptional:
    def test_an_int_outlet_drives_an_optional_inlet(self, graph_with_library_system: BaseGraph):
        graph = graph_with_library_system
        src_w, sink_w = _settings_node(graph, 0), _settings_node(graph, 300)
        src, sink = src_w.node, sink_w.node
        out_pid = _promote(src, "example_int", PortType.OUTLET)
        in_pid = _promote(sink, "optional_int", PortType.INLET)

        edge = graph.create_edge_wrapper(src_w.node_id, out_pid, sink_w.node_id, in_pid)
        assert edge is not None
        assert edge.state.is_valid()

        _drive(src, "example_int", 9, sink.ports[in_pid])
        assert sink.example.optional_int == 9

    def test_a_driven_optional_inlet_leaves_absence_behind(self, graph_with_library_system: BaseGraph):
        # While an inlet edge supplies values the field is never absent — the
        # graph owns the value, as it does for every promoted inlet.
        graph = graph_with_library_system
        src_w, sink_w = _settings_node(graph, 0), _settings_node(graph, 300)
        src, sink = src_w.node, sink_w.node
        out_pid = _promote(src, "example_int", PortType.OUTLET)
        in_pid = _promote(sink, "optional_int", PortType.INLET)
        graph.create_edge_wrapper(src_w.node_id, out_pid, sink_w.node_id, in_pid)

        assert sink.example.optional_int is None  # rests absent before anything drives it
        _drive(src, "example_int", 4, sink.ports[in_pid])
        assert sink.example.optional_int == 4
