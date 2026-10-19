"""``DataPort.set_widget_config`` — the seam a node changes its widget's config through."""

from unittest.mock import MagicMock

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.node.data import NodeData

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _di(library_system):
    """``NodeData`` resolves types through the ambient registries."""
    return


def _outlet(wrapper=None):
    node = NodeData("n", wrapper if wrapper is not None else MagicMock())
    port = node.add(FLOAT.as_outlet("value", widget_config={"properties": {"min": 0}}))
    return port


def test_set_widget_config_writes_a_property():
    port = _outlet()
    assert port.set_widget_config("max", 5) is True
    assert port.widget_config["properties"] == {"min": 0, "max": 5}


def test_set_widget_config_none_removes_the_key():
    port = _outlet()
    assert port.set_widget_config("min", None) is True
    assert "min" not in port.widget_config["properties"]
    assert port.set_widget_config("min", None) is False


def test_an_unchanged_value_does_not_redraw():
    wrapper = MagicMock()
    port = _outlet(wrapper)
    port._wrapper = wrapper
    assert port.set_widget_config("max", 5) is True
    assert port.set_widget_config("max", 5) is False
    assert wrapper.redraw.call_count == 1


def test_a_port_without_a_wrapper_still_updates():
    port = _outlet()
    port._wrapper = None
    assert port.set_widget_config("step", 0.5) is True
    assert port.widget_config["properties"]["step"] == 0.5


def test_a_shared_properties_dict_is_never_written():
    # Two ports declared from one module-level properties dict, as an author might.
    shared = {"min": 0, "max": 1}
    first = NodeData("a", MagicMock()).add(FLOAT.as_outlet("value", widget_config={"properties": shared}))
    second = NodeData("b", MagicMock()).add(FLOAT.as_outlet("value", widget_config={"properties": shared}))

    first.set_widget_config("max", 9)

    assert first.widget_config["properties"]["max"] == 9
    assert second.widget_config["properties"]["max"] == 1
    assert shared == {"min": 0, "max": 1}
