"""A swinglet: one port that may be either end of an edge."""

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.types import DataPort, PortType, StoreStrategy
from haywire.core.types.enums import ShowWidgetStrategy

from tests.conftest import make_node


def _port(type_cls, port_type, **kwargs) -> DataPort:
    return DataPort(
        registry_id="p",
        registry_key=type_cls.class_identity.registry_key,
        label="P",
        id="p",
        type_cls=type_cls,
        port_type=port_type,
        **kwargs,
    )


@pytest.mark.unit
def test_a_swinglet_is_both_an_inlet_and_an_outlet():
    port = _port(FLOAT, PortType.SWINGLET)
    assert port.is_inlet()
    assert port.is_outlet()
    assert port.is_swinglet()
    assert port._is_inlet is True


@pytest.mark.unit
def test_inlets_and_outlets_stay_one_direction():
    inlet, outlet = _port(FLOAT, PortType.INLET), _port(FLOAT, PortType.OUTLET)
    assert not inlet.is_outlet()
    assert not inlet.is_swinglet()
    assert not outlet.is_inlet()
    assert not outlet.is_swinglet()


@pytest.mark.unit
def test_adopting_the_swinglet_type_refreshes_the_cache():
    port = _port(FLOAT, PortType.OUTLET)
    port.adopt_port_type(PortType.SWINGLET)
    assert port._is_inlet is True


@pytest.mark.unit
def test_as_swinglet_defaults():
    kwargs = FLOAT.as_swinglet("s")["kwargs"]
    assert PortType(kwargs["port_type"]) is PortType.SWINGLET
    assert ShowWidgetStrategy(kwargs["show_widget"]) is ShowWidgetStrategy.NOT_LINKED
    assert StoreStrategy(kwargs["store_strategy"]) == StoreStrategy.HAS_WIDGET | StoreStrategy.NODE_SET


@pytest.mark.unit
def test_a_pooled_type_refuses_a_swinglet():
    from haybale_core.types import PooledType

    with pytest.raises(ValueError, match="inlets only"):
        PooledType[FLOAT].as_swinglet("s")  # type: ignore[valid-type]


@pytest.mark.integration
def test_get_ports_finds_a_swinglet_under_either_direction(graph_with_library_system):
    from haybale_testing.nodes.testbed.swinglet_probe import SwingletPassProbeNode

    node = make_node(graph_with_library_system, SwingletPassProbeNode.class_identity.registry_key).node
    for port_type in (PortType.INLET, PortType.OUTLET, PortType.SWINGLET):
        assert [p.id for p in node.get_ports(is_port_type=port_type)] == ["s"]


@pytest.mark.integration
def test_a_swinglet_round_trips_through_a_save(graph_with_library_system):
    from haybale_testing.nodes.testbed.swinglet_probe import SwingletPassProbeNode

    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler

    graph = graph_with_library_system
    node = make_node(graph, SwingletPassProbeNode.class_identity.registry_key)
    loaded = BaseGraph(filestem="g2", validation_scheduler=SyncScheduler())
    assert loaded.load_from_dict(graph.to_dict(include_data=True)) is True
    wrapper = loaded.get_node_wrapper(node.node_id)
    assert wrapper is not None
    assert wrapper.node.ports["s"].is_swinglet()
