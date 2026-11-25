"""A vector or matrix wired to a text inlet arrives as one line of text: ``(x, y)``, ``[[row], [row]]``."""

from __future__ import annotations

import importlib
from typing import Any

import numpy as np
import pytest

from haywire.barn.builtin.adapters import basic_adapters as ba
from haywire.barn.builtin.types import MAT3, MAT4, VEC2F, VEC2I, VEC3F, VEC3I, VEC4F, VEC4I
from haywire.core.settings.types import Mat3, Mat4, Vec2f, Vec2i, Vec3f, Vec3i, Vec4f, Vec4i
from tests.conftest import make_node

_CASES = [
    (ba.Vec2iToStringAdapter, VEC2I, Vec2i([1, -1]), "(1, -1)"),
    (ba.Vec3iToStringAdapter, VEC3I, Vec3i([1, -1, 0]), "(1, -1, 0)"),
    (ba.Vec4iToStringAdapter, VEC4I, Vec4i([7, 1, -1, 0]), "(7, 1, -1, 0)"),
    (ba.Vec2fToStringAdapter, VEC2F, Vec2f([0.5, -0.25]), "(0.5, -0.25)"),
    (ba.Vec3fToStringAdapter, VEC3F, Vec3f([0.5, -0.25, 1.0]), "(0.5, -0.25, 1.0)"),
    (ba.Vec4fToStringAdapter, VEC4F, Vec4f([1.0, 0.0, 0.5, -0.25]), "(1.0, 0.0, 0.5, -0.25)"),
    (
        ba.Mat3ToStringAdapter,
        MAT3,
        Mat3([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
        "[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]",
    ),
    (
        ba.Mat4ToStringAdapter,
        MAT4,
        Mat4([[1.0, 2.0, 3.0, 4.0], [0.5, 0.0, 0.0, 0.0], [0.0, 0.0, -1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]),
        "[[1.0, 2.0, 3.0, 4.0], [0.5, 0.0, 0.0, 0.0], [0.0, 0.0, -1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]",
    ),
]
_IDS = [case[1].__name__ for case in _CASES]


@pytest.mark.parametrize(("adapter_cls", "type_cls", "value", "text"), _CASES, ids=_IDS)
def test_converts_to_one_line_of_text(adapter_cls, type_cls, value, text):
    assert adapter_cls().convert(value) == text


@pytest.mark.parametrize(("adapter_cls", "type_cls", "value", "text"), _CASES, ids=_IDS)
def test_test_value_converts_and_has_the_type_length(adapter_cls, type_cls, value, text):
    adapter = adapter_cls()
    sample = adapter.get_test_value()
    assert type(sample) is type(value)
    assert len(sample) == len(value)
    assert isinstance(adapter.convert(sample), str)


def test_a_float_vector_reads_integers_and_numpy_floats_as_floats():
    assert ba.Vec2fToStringAdapter().convert(Vec2f([1, np.float32(0.3)])) == "(1.0, 0.3)"


def test_an_integer_vector_reads_numpy_integers_as_plain_integers():
    assert ba.Vec2iToStringAdapter().convert(Vec2i([np.int64(3), np.int32(-4)])) == "(3, -4)"


def test_numpy_matrix_rows_read_as_float_rows():
    assert (
        ba.Mat3ToStringAdapter().convert(Mat3(np.eye(3)))
        == "[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]"
    )


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


@pytest.mark.integration
@pytest.mark.parametrize(("adapter_cls", "type_cls", "value", "text"), _CASES, ids=_IDS)
def test_an_outlet_feeds_a_print_message_through_one_adapter(
    graph_with_library_system, adapter_cls, type_cls, value, text
):
    graph = graph_with_library_system
    source = _add(graph, "haybale_testing.nodes.testbed.edge_link_probe", "EdgeLinkProbeNode")
    source.add(type_cls.as_outlet("shape"))
    printer = _add(graph, "haybale_core.nodes.print", "PrintNode")

    edge = graph.create_edge_wrapper(source.node_id, "shape", printer.node_id, "message")
    assert edge is not None
    assert edge.is_valid()
    assert edge.edge.chain_adapter_keys == [adapter_cls.class_identity.registry_key]

    source.out("shape", value)
    assert printer.ports["message"].get_value() == text
