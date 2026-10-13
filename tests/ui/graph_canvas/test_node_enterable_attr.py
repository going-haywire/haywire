"""``data-node-enterable`` marks the cards canvas.vue lets a double-click enter."""

import haywire.core.graph.editor  # noqa: F401  (circular-import guard)

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.editors.graph_canvas.ui_node import UINode

pytestmark = pytest.mark.unit


class _PlainNode:
    class_identity = SimpleNamespace(_is_macro_node=False)
    identity = SimpleNamespace(_is_graph_node=False)


class _GroupNode:
    class_identity = SimpleNamespace(_is_macro_node=False)
    identity = SimpleNamespace(_is_graph_node=True)


class _PlacementNode:
    class_identity = SimpleNamespace(_is_macro_node=True)
    identity = SimpleNamespace(_is_graph_node=False)


def _stamped(node: Any) -> dict:
    ui_node = UINode.__new__(UINode)  # bypass __init__; only the stamp is exercised
    ui_node.wrapper = MagicMock()
    ui_node.wrapper.node = node()
    ui_node.container = MagicMock()
    ui_node.container._props = {}
    ui_node._apply_enterable_attr()
    return cast(dict, ui_node.container._props)


def test_graph_node_cards_are_enterable():
    assert _stamped(_GroupNode)["data-node-enterable"] == "true"
    assert _stamped(_PlacementNode)["data-node-enterable"] == "true"


def test_a_plain_node_is_not_enterable():
    assert "data-node-enterable" not in _stamped(_PlainNode)
