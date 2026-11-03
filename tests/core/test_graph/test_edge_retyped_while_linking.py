"""A new edge whose port is retyped before the next validation pass is built again for the new type."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from haywire.barn.builtin.types import PATH
from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import ThreadingTimerScheduler
from haywire.core.types.enums import Propagation

from tests.conftest import make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"


@pytest.fixture
def held_graph(library_system) -> Iterator[BaseGraph]:
    graph = BaseGraph(
        filestem="g", validation_scheduler=ThreadingTimerScheduler(), validation_delay_ms=60_000
    )
    yield graph
    graph._validation.clear()
    graph.cleanup()


def test_a_port_retyped_after_its_new_edge_was_built_rebuilds_the_edge(held_graph: BaseGraph):
    source = make_node(held_graph, _ADD)
    sink = make_node(held_graph, _ADD)
    held_graph._validation.force_immediate_validation()
    # Lazy, so re-adding the port does not push a value through the old chain.
    edge = held_graph.create_edge_wrapper(
        source.node_id, "result", sink.node_id, "value_a", propagation=Propagation.LAZY
    )
    assert edge is not None
    assert edge.is_valid()

    # As a node does from on_connect: same port id, a type with no way into FLOAT.
    with source.node.rejig(include=["result"]):
        source.node.add(PATH.as_outlet("result", label="Result"))
    assert not edge.built_for_current_ports()

    held_graph._validation.force_immediate_validation()

    assert edge.built_for_current_ports()
    assert not edge.is_valid()


def test_an_edge_built_for_its_ports_is_left_alone(held_graph: BaseGraph):
    source = make_node(held_graph, _ADD)
    sink = make_node(held_graph, _ADD)
    edge = held_graph.create_edge_wrapper(source.node_id, "result", sink.node_id, "value_a")
    assert edge is not None

    held_graph._validation.force_immediate_validation()

    assert edge.built_for_current_ports()
    assert edge.is_valid()
