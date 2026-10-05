"""The link ceiling: how many edges a port may hold, set by the mechanism and narrowed by the port."""

import pytest

from haywire.barn.builtin.types import ADD, CALLBACK, EXEC, FLOAT, INT, OPTIONAL
from haywire.core.types import DataPort, PortType

from tests.conftest import make_edge, make_node

OUTLET, INLET = PortType.OUTLET, PortType.INLET


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


def _array(element):
    from haybale_core.types import ArrayType

    return ArrayType[element]  # type: ignore[valid-type]


def _pooled(element):
    from haybale_core.types import PooledType

    return PooledType[element]  # type: ignore[valid-type]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("type_cls", "port_type", "many"),
    [
        (FLOAT, OUTLET, True),
        (FLOAT, INLET, False),
        (EXEC, OUTLET, False),
        (EXEC, INLET, True),
        (CALLBACK, OUTLET, True),
        (CALLBACK, INLET, False),
        (ADD, OUTLET, True),
        (ADD, INLET, False),
        (ADD[EXEC], INLET, True),
        (OPTIONAL[INT], OUTLET, True),
        (OPTIONAL[INT], INLET, False),
    ],
)
def test_the_ceiling_follows_the_mechanism(type_cls, port_type, many):
    assert _port(type_cls, port_type).takes_many_links is many


@pytest.mark.unit
def test_a_container_takes_its_elements_ceiling():
    assert _port(_array(FLOAT), OUTLET).takes_many_links is True
    assert _port(_array(FLOAT), INLET).takes_many_links is False


@pytest.mark.unit
@pytest.mark.parametrize("element", [FLOAT, CALLBACK])
def test_a_pooled_inlet_takes_many(element):
    assert _port(_pooled(element), INLET).takes_many_links is True


@pytest.mark.unit
@pytest.mark.parametrize(("type_cls", "port_type"), [(FLOAT, OUTLET), (EXEC, INLET), (CALLBACK, OUTLET)])
def test_single_link_narrows_a_many_ceiling_to_one(type_cls, port_type):
    assert _port(type_cls, port_type, single_link=True).takes_many_links is False


@pytest.mark.unit
def test_single_link_is_saved_only_when_set():
    assert "single_link" not in _port(FLOAT, OUTLET).to_dict()["kwargs"]
    assert _port(FLOAT, OUTLET, single_link=True).to_dict()["kwargs"]["single_link"] is True


@pytest.mark.integration
def test_a_saved_allow_multiple_links_is_ignored_on_load(graph_with_library_system):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    node = make_node(graph, TestAddFloatNode.class_identity.registry_key)
    data = graph.to_dict()
    for spec in data["nodes"][node.node_id]["node_data"]["ports"].values():
        spec["kwargs"]["allow_multiple_links"] = True

    graph.clear()
    graph.load_from_dict(data)

    assert graph.node_wrappers[node.node_id].node.ports["value_a"].takes_many_links is False


@pytest.mark.integration
def test_a_narrowed_outlet_keeps_one_linked_edge(graph_with_library_system):
    from haybale_testing.nodes.testbed.math_op_node import TestAddFloatNode

    graph = graph_with_library_system
    key = TestAddFloatNode.class_identity.registry_key
    source, first, second = (make_node(graph, key) for _ in range(3))
    source.node.ports["result"].single_link = True

    make_edge(graph, source.node_id, "result", first.node_id, "value_a")
    newest = make_edge(graph, source.node_id, "result", second.node_id, "value_a")
    graph.force_validation()

    linked = source.node.ports["result"]._linked_edges
    assert len(linked) == 1
    assert list(linked) == [newest.edge_id]
