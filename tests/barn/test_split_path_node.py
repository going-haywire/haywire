"""Split Path: a volume path into volume, folder, stem, extension and parent."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from haywire.core.volumes import VolumePath
from tests.conftest import make_node

pytestmark = pytest.mark.integration

SCANS = "user:volume:scans"


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _split(graph: Any, path: VolumePath) -> Any:
    node = _add(graph, "haybale_core.nodes.split_path", "SplitPathNode")
    node.worker(MagicMock(), path=path)
    return node


def _out(node: Any, name: str) -> Any:
    return node.ports[name].get_value()


def test_splits_nested(graph_with_library_system):
    node = _split(graph_with_library_system, VolumePath(SCANS, "a/b/x.png"))
    assert _out(node, "folder") == "a/b"
    assert _out(node, "stem") == "x"
    assert _out(node, "extension") == ".png"
    assert _out(node, "parent") == VolumePath(SCANS, "a/b")
    assert _out(node, "volume") == VolumePath(SCANS, "")


def test_root_file(graph_with_library_system):
    node = _split(graph_with_library_system, VolumePath(SCANS, "x.png"))
    assert _out(node, "folder") == ""
    assert _out(node, "parent") == VolumePath(SCANS, "")


@pytest.mark.parametrize("relative", ["a/b/x.png", "x.png", "a/x"])
def test_round_trips_through_output_path(graph_with_library_system, relative):
    graph = graph_with_library_system
    original = VolumePath(SCANS, relative)
    split = _split(graph, original)
    out = _add(graph, "haybale_core.nodes.output_path", "OutputPathNode")
    out.worker(
        MagicMock(),
        folder=_out(split, "volume"),
        subdir=_out(split, "folder"),
        stem=_out(split, "stem"),
        extension=_out(split, "extension"),
    )
    assert out.ports["path"].get_value() == original
