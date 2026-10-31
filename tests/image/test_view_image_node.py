"""View Image: passes the image on, and its Mode sets the viewer's mode."""

import importlib
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from tests.conftest import make_node

pytestmark = pytest.mark.integration


def _view(graph: Any) -> Any:
    cls = importlib.import_module("haybale_image.nodes.view_image").ViewImageNode
    wrapper = make_node(graph, cls.class_identity.registry_key, position=(0, 0))
    assert isinstance(wrapper.node, cls), "an unknown key yields an ErrorNode"
    return wrapper.node


def _mode(node: Any) -> Any:
    return node.ports["image"].widget_config["properties"]["mode"]


def test_view_image_passes_image_through(graph_with_library_system):
    value_mod = importlib.import_module("haybale_image.value")
    node = _view(graph_with_library_system)
    img = value_mod.ImageValue.from_array(np.zeros((4, 6, 3), np.uint8))
    assert node.worker(MagicMock(), image=img) == "next"
    assert node.ports["image_out"].get_value() is img


def test_view_image_widget_is_image_viewer(graph_with_library_system):
    widget_cls = importlib.import_module("haybale_image.widgets.image_viewer_widget").ImageViewerWidget
    node = _view(graph_with_library_system)
    assert node.ports["image"].widget_key == widget_cls.class_identity.registry_key
    assert _mode(node) == node.viewer.mode


def test_mode_change_sets_viewer_mode(graph_with_library_system):
    node = _view(graph_with_library_system)
    node.viewer.mode = "still"
    assert _mode(node) == "still"
    node.viewer.mode = "stream"
    assert _mode(node) == "stream"


def test_enlarge_and_zoom_reach_the_viewer(graph_with_library_system):
    node = _view(graph_with_library_system)
    props = lambda: node.ports["image"].widget_config["properties"]  # noqa: E731

    assert (props()["enlarge"], props()["zoom"]) == (3.0, 1.0)

    node.viewer.enlarge = 4.0
    node.viewer.zoom = 2.5

    assert (props()["enlarge"], props()["zoom"]) == (4.0, 2.5)
