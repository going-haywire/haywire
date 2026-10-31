"""Resolve Path: the absolute location of a volume path on this machine."""

import importlib
from typing import Any

import pytest

from haywire.core.volumes import VolumeEscapeError, VolumePath, VolumeUndefinedError, get_volume_store
from tests.conftest import make_node

pytestmark = pytest.mark.integration

SCANS = "user:volume:scans"


def _node(graph: Any) -> Any:
    cls = importlib.import_module("haybale_core.nodes.resolve_path").ResolvePathNode
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


@pytest.fixture
def scans(tmp_path):
    get_volume_store().add(SCANS, label="Scans", description="", location=tmp_path)
    return tmp_path


def test_resolves_to_the_absolute_path(graph_with_library_system, scans):
    node = _node(graph_with_library_system)
    node.worker(None, path=VolumePath(SCANS, "raw/a.png"))
    assert node.ports["resolved"].get_value() == str(scans.resolve() / "raw" / "a.png")


def test_a_missing_file_still_resolves(graph_with_library_system, scans):
    node = _node(graph_with_library_system)
    node.worker(None, path=VolumePath(SCANS, "nowhere.png"))
    assert node.ports["resolved"].get_value().endswith("nowhere.png")


def test_undefined_volume_raises(graph_with_library_system, scans):
    with pytest.raises(VolumeUndefinedError):
        _node(graph_with_library_system).worker(None, path=VolumePath("user:volume:nowhere", "a"))


def test_escape_raises(graph_with_library_system, scans):
    with pytest.raises(VolumeEscapeError):
        _node(graph_with_library_system).worker(None, path=VolumePath(SCANS, "../x"))
