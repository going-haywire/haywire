"""Load Image and Image Info: volume-resolved decode and the info outlets."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from haywire.core.volumes import VolumePath, VolumeUndefinedError, get_volume_store
from tests.conftest import make_node

pytestmark = pytest.mark.integration

SCANS = "user:volume:scans"


def _add(graph: Any, module: str, name: str) -> Any:
    cls = getattr(importlib.import_module(module), name)
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _load(graph: Any) -> Any:
    return _add(graph, "haybale_image.nodes.load_image", "LoadImageNode")


def _info(graph: Any) -> Any:
    return _add(graph, "haybale_image.nodes.image_info", "ImageInfoNode")


@pytest.fixture
def scans(tmp_path):
    cv2 = importlib.import_module("cv2")
    bgr = np.zeros((4, 6, 3), np.uint8)
    bgr[..., 2] = 200  # red in BGR
    cv2.imwrite(str(tmp_path / "rgb.png"), bgr)
    cv2.imwrite(str(tmp_path / "gray16.png"), np.full((3, 5), 1000, np.uint16))
    get_volume_store().add(SCANS, label="Scans", description="", location=tmp_path)
    return tmp_path


def test_loads_png_as_rgb(graph_with_library_system, scans):
    node = _load(graph_with_library_system)
    node.worker(MagicMock(), path=VolumePath(SCANS, "rgb.png"))
    img = node.ports["image"].get_value()
    assert (img.width, img.height) == (6, 4)
    assert str(img.layout) == "rgb"


def test_missing_file_raises_naming_it(graph_with_library_system, scans):
    node = _load(graph_with_library_system)
    with pytest.raises(FileNotFoundError, match="nope.png"):
        node.worker(MagicMock(), path=VolumePath(SCANS, "nope.png"))


def test_undefined_volume_raises(graph_with_library_system, scans):
    node = _load(graph_with_library_system)
    with pytest.raises(VolumeUndefinedError):
        node.worker(MagicMock(), path=VolumePath("user:volume:nowhere", "a.png"))


def test_image_info_outlets(graph_with_library_system, scans):
    graph = graph_with_library_system
    load, info = _load(graph), _info(graph)
    load.worker(MagicMock(), path=VolumePath(SCANS, "gray16.png"))
    info.worker(MagicMock(), image=load.ports["image"].get_value())
    got = {k: info.ports[k].get_value() for k in ("width", "height", "layout", "depth")}
    assert got == {"width": 5, "height": 3, "layout": "gray", "depth": 16}
