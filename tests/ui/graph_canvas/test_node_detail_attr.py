"""UINode stamps data-node-props-detail on the container — the mechanism
canvas.vue's [data-node-props-detail] CSS rules key off. Mirrors
_apply_locked_attr's existing test coverage pattern (see test_node_size_apply.py
for the bypass-__init__ construction style this follows).
"""

from typing import Any, cast

from unittest.mock import MagicMock

from haybale_graph_editor.editors.graph_canvas.ui_node import UINode

from haywire.core.types import NodeDetail


def _ui_node_with_detail(detail: str) -> UINode:
    node = UINode.__new__(UINode)  # bypass __init__; we only exercise _apply_detail_attr
    node.wrapper = MagicMock()
    node.wrapper.node.props.detail = detail
    container = MagicMock()
    container._props = {}
    node.container = container
    return node


def test_container_carries_the_resolved_rank():
    n = _ui_node_with_detail(NodeDetail.FULL.value)
    n._apply_detail_attr()
    assert cast(Any, n.container)._props["data-node-props-detail"] == NodeDetail.FULL.value
    cast(Any, n.container).update.assert_called()


def test_attr_updates_when_detail_changes():
    n = _ui_node_with_detail(NodeDetail.FULL.value)
    n._apply_detail_attr()

    n.wrapper.node.props.detail = NodeDetail.PINS.value
    n._apply_detail_attr()

    assert cast(Any, n.container)._props["data-node-props-detail"] == NodeDetail.PINS.value


def test_unrecognised_value_degrades_to_full():
    """coerce() is used, not a raw pass-through — an old 3-rank saved value
    must not reach the DOM as a wire string canvas.vue has no CSS rule for."""
    n = _ui_node_with_detail("compact")
    n._apply_detail_attr()
    assert cast(Any, n.container)._props["data-node-props-detail"] == NodeDetail.FULL.value
