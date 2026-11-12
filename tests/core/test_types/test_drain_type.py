"""DRAIN[T] and DrainField: the queue, its limit, the port rules, and a real edge feeding it."""

from __future__ import annotations

import threading

import pytest

from haywire.barn.builtin.types import CALLBACK, EXEC, FLOAT
from haywire.barn.builtin.wires import DataWire
from haywire.core.types import DataPort, Drained, PortType, Propagation
from haywire.core.types.enums import StoreStrategy

from haybale_core.types import DRAIN
from haybale_core.types.drain_type import DEFAULT_MAX_LEN

from tests.conftest import make_edge, make_node

_ADD = "haybale-testing:node:TestAddFloatNode"


def _field(max_len: int | None = None):
    return DRAIN[FLOAT].create_field(None if max_len is None else {"max_len": max_len})


def _port(type_cls, port_type=PortType.INLET) -> DataPort:
    return DataPort(
        registry_id="p",
        registry_key=type_cls.class_identity.registry_key,
        label="P",
        id="p",
        type_cls=type_cls,
        port_type=port_type,
    )


@pytest.mark.unit
class TestTheQueue:
    def test_keeps_every_value_in_order(self):
        f = _field()
        for v in (1.0, 2.0, 3.0):
            f.set_value(v, source_id="e")

        assert f.take() == [1.0, 2.0, 3.0]

    def test_keeps_equal_values_each(self):
        f = _field()
        f.set_value(1.0, source_id="e")
        f.set_value(1.0, source_id="e")

        assert f.take() == [1.0, 1.0]

    def test_take_empties_it(self):
        f = _field()
        f.set_value(1.0, source_id="e")
        f.take()

        batch = f.take()

        assert batch == []
        assert batch.dropped == 0
        assert not f.has_data()

    def test_take_returns_drained(self):
        assert isinstance(_field().take(), Drained)

    def test_get_value_looks_without_taking(self):
        f = _field()
        f.set_value(1.0, source_id="e")

        assert f.get_value() == [1.0]
        assert f.take() == [1.0]

    def test_ignores_absence(self):
        f = _field()
        f.set_value(None, source_id="e")

        assert f.take() == []

    def test_refuses_a_write_without_a_source(self):
        with pytest.raises(ValueError, match="only from its edge"):
            _field().set_value(1.0)

    def test_reset_and_remove_source_empty_it(self):
        f = _field()
        f.set_value(1.0, source_id="e")
        f.reset()
        assert f.take() == []

        f.set_value(1.0, source_id="e")
        f.remove_source("e")
        assert f.take() == []

    def test_observers_get_the_value_that_joined(self):
        f = _field()
        seen = []
        f.add_observer(lambda change: seen.append(change.value))

        f.set_value(1.0, source_id="e")
        f.set_value(2.0, source_id="e")

        assert seen == [1.0, 2.0]


@pytest.mark.unit
class TestTheLimit:
    def test_defaults_to_the_declared_max_len(self):
        assert _field().max_len == DEFAULT_MAX_LEN

    def test_takes_max_len_from_the_default(self):
        assert _field(3).max_len == 3

    def test_refuses_a_max_len_below_one(self):
        with pytest.raises(ValueError, match="at least 1"):
            _field(0)

    def test_drops_the_oldest_and_counts_it(self):
        f = _field(2)
        for v in (1.0, 2.0, 3.0, 4.0):
            f.set_value(v, source_id="e")

        batch = f.take()

        assert batch == [3.0, 4.0]
        assert batch.dropped == 2

    def test_the_count_starts_over_after_a_take(self):
        f = _field(1)
        f.set_value(1.0, source_id="e")
        f.set_value(2.0, source_id="e")
        f.take()
        f.set_value(3.0, source_id="e")

        assert f.take().dropped == 0


@pytest.mark.unit
class TestThreads:
    def test_nothing_is_lost_or_repeated_while_taking_concurrently(self):
        writes = 5000
        f = _field(writes)
        taken: list[float] = []
        done = threading.Event()

        def produce():
            for i in range(writes):
                f.set_value(float(i), source_id="e")
            done.set()

        def consume():
            while not done.is_set():
                taken.extend(f.take())
            taken.extend(f.take())

        threads = [threading.Thread(target=produce), threading.Thread(target=consume)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert taken == [float(i) for i in range(writes)]


@pytest.mark.unit
class TestThePort:
    def test_is_the_elements_pin(self):
        port = _port(DRAIN[FLOAT])

        assert port.wire_type is not None
        assert port.wire_type.id == DataWire.id
        assert port.stored_type is FLOAT

    def test_queues_and_takes_one_edge(self):
        port = _port(DRAIN[FLOAT])

        assert port.queues_values is True
        assert port.takes_many_links is False
        assert port.data.accepts_own_value() is False

    def test_is_never_saved(self):
        spec = DRAIN[FLOAT].as_inlet("q")

        assert spec["kwargs"]["store_strategy"] is StoreStrategy.NEVER

    def test_refuses_an_outlet(self):
        with pytest.raises(ValueError, match="inlets only"):
            DRAIN[FLOAT].as_outlet("q")

    @pytest.mark.parametrize("element", [EXEC, CALLBACK])
    def test_refuses_an_element_that_carries_no_values(self, element):
        with pytest.raises(ValueError, match="carries values"):
            DRAIN._configure_port(_port(DRAIN[element]))  # type: ignore[valid-type]


@pytest.mark.integration
class TestAnEdgeIntoADrainInlet:
    @pytest.fixture
    def fed(self, graph_with_library_system):
        graph = graph_with_library_system
        source, sink = make_node(graph, _ADD), make_node(graph, _ADD)
        sink.node.add(DRAIN[FLOAT].as_inlet("queue"))
        edge = make_edge(graph, source.node_id, "result", sink.node_id, "queue")
        graph.force_validation()
        return graph, source, sink, edge

    def test_validates_and_is_locked_eager(self, fed):
        _graph, _source, _sink, edge = fed

        assert edge.state.is_formally_validated
        assert edge.propagation is Propagation.EAGER

    def test_every_outlet_write_reaches_the_node(self, fed):
        _graph, source, sink, _edge = fed
        for v in (1.0, 2.0, 2.0):
            source.node.ports["result"].set_value(v)

        assert sink.node.drain("queue") == [1.0, 2.0, 2.0]
        assert sink.node.drain("queue") == []

    def test_linking_queues_nothing(self, fed):
        _graph, _source, sink, _edge = fed

        assert sink.node.drain("queue") == []

    def test_another_edge_on_the_outlet_queues_nothing(self, fed):
        graph, source, sink, _edge = fed
        source.node.ports["result"].set_value(1.0)
        other = make_node(graph, _ADD)

        make_edge(graph, source.node_id, "result", other.node_id, "value_a")
        graph.force_validation()

        assert sink.node.drain("queue") == [1.0]
        assert other.node.ports["value_a"].get_value() == pytest.approx(1.0)

    def test_removing_the_edge_empties_the_queue(self, fed):
        graph, source, sink, edge = fed
        source.node.ports["result"].set_value(1.0)

        graph.remove_edge_wrapper(edge.edge_id)

        assert sink.node.drain("queue") == []
