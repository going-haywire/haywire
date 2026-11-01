"""ModelRef value and the MODEL_REF type."""

import json
from typing import Any

import pytest

from haybale_models.value import ModelRef

CATALOG = ModelRef(catalog="haybale-x:catalog:4x-Demo")
FILE = ModelRef(urls=("hf://org/repo/m.safetensors@main",), sha256="a" * 64, size=10, label="m")


def test_round_trip_both_forms():
    for ref in (CATALOG, FILE, ModelRef.empty()):
        assert ModelRef.from_dict(json.loads(json.dumps(ref.to_dict()))) == ref


def test_forms_and_accessors():
    assert CATALOG.is_catalog
    assert not CATALOG.is_file
    assert not CATALOG.is_empty
    assert FILE.is_file
    assert not FILE.is_catalog
    assert FILE.source == "hf://org/repo/m.safetensors@main"
    assert ModelRef().is_empty
    assert ModelRef().source is None
    assert ModelRef(sha256="b" * 64, size=3, label="x.pth").is_file  # picked from a volume


def test_to_dict_omits_empty_fields():
    assert ModelRef().to_dict() == {}
    assert CATALOG.to_dict() == {"catalog": "haybale-x:catalog:4x-Demo"}
    assert ModelRef.from_dict({}) == ModelRef.empty()


def test_both_forms_at_once_raises():
    with pytest.raises(ValueError, match="catalog reference"):
        ModelRef(catalog="a:catalog:b", urls=("https://x/y.pth",))


def test_pinned_fills_digest_and_size():
    ref = ModelRef(urls=("https://x/y.pth",)).pinned("c" * 64, 7)
    assert (ref.sha256, ref.size, ref.urls) == ("c" * 64, 7, ("https://x/y.pth",))


def _type(library_system: Any) -> Any:
    return library_system.get_type_registry().get_type_class("haybale-models:type:MODEL_REF")


def _node(graph: Any) -> Any:
    from haybale_testing.nodes.testbed.edge_link_test import EdgeLinkTestNode

    return graph.create_node_wrapper(EdgeLinkTestNode.class_identity.registry_key, position=(0, 0))


def _port(graph: Any, library_system: Any, **kwargs: Any) -> Any:
    wrapper = _node(graph)
    wrapper.node.add(_type(library_system).as_inlet("model", label="Model", **kwargs))
    return wrapper, wrapper.node.ports["model"]


@pytest.mark.integration
def test_default_is_empty(graph_with_library_system, library_system):
    _, port = _port(graph_with_library_system, library_system)
    assert port.get_value() == ModelRef.empty()


@pytest.mark.integration
@pytest.mark.parametrize("wrap", [False, True])
def test_field_converts_dict_writes(graph_with_library_system, library_system, wrap):
    _, port = _port(graph_with_library_system, library_system)
    port.set_value({"value": FILE.to_dict()} if wrap else FILE.to_dict())
    assert port.get_value() == FILE
    assert port.data.to_dict()["value"] == FILE.to_dict()


@pytest.mark.integration
def test_port_gets_type_widget_defaults(graph_with_library_system, library_system):
    assert _type(library_system).class_identity.widget_key == "haybale-models:widget:ModelRefWidget"
    _, port = _port(graph_with_library_system, library_system)
    props = port.widget_config["properties"]
    assert props["filter"] == {}
    assert props["prefer"] == []
    config = {"properties": {"filter": {"purpose": ["SR"]}, "prefer": [{"precision": "fp16"}, {}]}}
    _, port = _port(graph_with_library_system, library_system, widget_config=config)
    props = port.widget_config["properties"]
    assert props["filter"] == {"purpose": ["SR"]}
    assert props["prefer"] == [{"precision": "fp16"}, {}]


@pytest.mark.integration
def test_default_is_empty_and_graph_round_trips(graph_with_library_system, library_system):
    from haywire.core.types.port import DataPort

    wrapper, port = _port(graph_with_library_system, library_system)
    port.set_value(FILE.to_dict())
    spec = json.loads(json.dumps(port.to_dict(include_data=True)))
    assert spec["field_data"] == {"value": FILE.to_dict()}
    node = wrapper.node
    rebuilt = DataPort.from_spec(spec, node._type_registry, wrapper, node)
    assert rebuilt.get_value() == FILE
    assert rebuilt.type_cls is _type(library_system)
