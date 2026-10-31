"""Create Folder: mkdir -p inside a volume; refuses to create a missing volume root."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from haywire.core.volumes import VolumeEscapeError, VolumePath, get_volume_store
from tests.conftest import make_node

pytestmark = pytest.mark.integration

SCANS = "user:volume:scans"


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _node(graph: Any) -> Any:
    return _add(graph, "haybale_core.nodes.create_folder", "CreateFolderNode")


def _define(location) -> None:
    get_volume_store().add(SCANS, label="Scans", description="", location=location)


def test_creates_nested(graph_with_library_system, tmp_path):
    _define(tmp_path)
    node = _node(graph_with_library_system)
    target = VolumePath(SCANS, "a/b")
    assert node.worker(MagicMock(), path=target) == "next"
    assert (tmp_path / "a" / "b").is_dir()
    assert node.ports["folder"].get_value() == target


def test_existing_is_noop(graph_with_library_system, tmp_path):
    _define(tmp_path)
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "keep.txt").write_bytes(b"x")
    _node(graph_with_library_system).worker(MagicMock(), path=VolumePath(SCANS, "a"))
    assert (tmp_path / "a" / "keep.txt").exists()


def test_missing_volume_root_raises_and_creates_nothing(graph_with_library_system, tmp_path):
    location = tmp_path / "unmounted"
    _define(location)
    with pytest.raises(FileNotFoundError, match="volume 'scans' location .*unmounted"):
        _node(graph_with_library_system).worker(MagicMock(), path=VolumePath(SCANS, "a/b"))
    assert not location.exists()
    assert not any(p.is_dir() for p in tmp_path.iterdir())


def test_escape_raises(graph_with_library_system, tmp_path):
    _define(tmp_path)
    with pytest.raises(VolumeEscapeError):
        _node(graph_with_library_system).worker(MagicMock(), path=VolumePath(SCANS, "../x"))


def test_wires_from_output_path_folder(graph_with_library_system):
    graph = graph_with_library_system
    source = _add(graph, "haybale_core.nodes.output_path", "OutputPathNode")
    node = _node(graph)
    edge = graph.create_edge_wrapper(source.node_id, "out_folder", node.node_id, "path")
    assert edge is not None
    assert node.ports["path"].data.has_linked_value()
