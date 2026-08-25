from typing import Any, cast

import haywire.core.graph.editor  # noqa: F401  (circular-import guard)

from unittest.mock import MagicMock

from haybale_graph_editor.editors.graph_canvas.ui_node import UINode


def _ui_node_with_props(
    size_adapt: str,
    width: float,
    height: float,
    *,
    node_theme: str = "",
    color_override: str | None = None,
) -> UINode:
    node = UINode.__new__(UINode)  # bypass __init__; we only exercise _apply_slot_style
    node.wrapper = MagicMock()
    node.wrapper.node.props.size_adapt = size_adapt
    node.wrapper.node.props.width = width
    node.wrapper.node.props.height = height
    # Explicit, not left to MagicMock: an auto-created attribute is truthy, so
    # every size test would silently grow appearance declarations.
    node.wrapper.node.props.node_theme = node_theme
    node.wrapper.node.props.color_override = color_override
    node.wrapper.graph.props.node_theme = ""
    node._node_id = "n1"
    slot = MagicMock()
    slot._props = {}
    node.container_slot = slot
    return node


def _style_str(n: UINode) -> str:
    # _apply_slot_style writes with replace= so the slot's inline style is authoritative.
    return cast(Any, n.container_slot).style.call_args.kwargs["replace"]


def test_apply_size_manual_writes_both_axes_as_minimums():
    n = _ui_node_with_props("manual", 300.0, 180.0)
    n._apply_slot_style()
    style = _style_str(n)
    assert "min-width: 300" in style
    assert "min-height: 180" in style
    assert cast(Any, n.container_slot)._props["data-size-adapt"] == "manual"
    cast(Any, n.container_slot).update.assert_called()


def test_apply_size_manual_width_writes_only_width_min():
    n = _ui_node_with_props("manual_width", 300.0, 180.0)
    n._apply_slot_style()
    style = _style_str(n)
    assert "min-width: 300" in style
    assert "height" not in style  # height axis left to content


def test_apply_size_never_clips():
    # Manual sizes are MINIMUMS: content needing more space expands the node.
    # Regression: earlier schemes clipped the slot (overflow hidden/clip),
    # cropping the pins straddling the card edge and the edges attached to
    # them. No overflow declaration — and no hard width/height — may appear.
    for mode in ("manual", "manual_width", "manual_height"):
        n = _ui_node_with_props(mode, 300.0, 180.0)
        n._apply_slot_style()
        style = _style_str(n)
        assert "overflow" not in style, f"{mode}: {style!r}"
        for decl in style.split(";"):
            prop = decl.split(":")[0].strip()
            assert prop not in ("width", "height"), f"{mode} wrote hard {prop}: {style!r}"


def test_apply_size_auto_clears_inline_size():
    n = _ui_node_with_props("auto", 300.0, 180.0)
    n._apply_slot_style()
    style = _style_str(n)
    # auto axes carry no inline width/height (empty declarations)
    assert "width:" not in style
    assert "height:" not in style
    assert cast(Any, n.container_slot)._props["data-size-adapt"] == "auto"


def test_size_change_restyles_slot_without_redraw():
    n = _ui_node_with_props("manual", 300.0, 180.0)
    n.render = MagicMock()  # type: ignore[method-assign]  # spy: must NOT be called by a size change

    n.wrapper.node.props.width = 260.0
    n._on_slot_field_change(260.0, 300.0)  # simulate a width change to 260

    n.render.assert_not_called()
    cast(Any, n.container_slot).update.assert_called()


def test_subscribe_slot_fields_wires_size_and_appearance():
    n = _ui_node_with_props("auto", 200.0, 200.0)
    n.wrapper.node.props.subscribe_field = MagicMock()  # type: ignore[method-assign]
    n._subscribe_slot_fields()
    watched = {call.args[0] for call in n.wrapper.node.props.subscribe_field.call_args_list}
    assert watched == {"width", "height", "size_adapt", "node_theme", "color_override"}


# ---------------------------------------------------------------------------
# Appearance — the same style-write path as size, deliberately
# ---------------------------------------------------------------------------


def test_color_override_writes_the_node_bg_var():
    n = _ui_node_with_props("auto", 200.0, 200.0, color_override="#ff0000ff")
    n._apply_slot_style()
    assert "--hw-node-bg: #ff0000ff" in _style_str(n)


def test_empty_color_override_writes_nothing():
    """Emptiness IS the unset mechanism — no is_locally_set involved."""
    for empty in (None, ""):
        n = _ui_node_with_props("auto", 200.0, 200.0, color_override=empty)
        n._apply_slot_style()
        assert "--hw-node-bg" not in _style_str(n)


def test_clearing_a_colour_clears_its_var():
    """replace= is what makes this work: the write is authoritative, so a
    cleared field leaves no stale declaration behind."""
    n = _ui_node_with_props("auto", 200.0, 200.0, color_override="#ff0000ff")
    n._apply_slot_style()
    assert "--hw-node-bg" in _style_str(n)

    n.wrapper.node.props.color_override = None
    n._apply_slot_style()
    assert "--hw-node-bg" not in _style_str(n)


def test_node_theme_equal_to_graph_writes_nothing():
    """The divergence rule: identical values produce identical CSS, so the
    node contributes nothing and the graph tier shows through. This is what
    keeps a 200-node graph from writing 200 identical declaration sets."""
    n = _ui_node_with_props("auto", 200.0, 200.0, node_theme="some:theme:key")
    n.wrapper.graph.props.node_theme = "some:theme:key"
    n._apply_slot_style()
    assert _style_str(n) == ""


def test_unresolvable_node_theme_degrades_to_nothing():
    """A bad key must not take the node's render down — the tier above shows
    through instead."""
    n = _ui_node_with_props("auto", 200.0, 200.0, node_theme="no:such:theme")
    n._apply_slot_style()
    assert "--hw-node" not in _style_str(n)


def test_appearance_change_restyles_slot_without_redraw():
    """The property that lets the properties panel keep focus mid-edit."""
    n = _ui_node_with_props("auto", 200.0, 200.0)
    n.render = MagicMock()  # type: ignore[method-assign]

    n.wrapper.node.props.color_override = "#00ff00ff"
    n._on_slot_field_change("#00ff00ff", None)

    n.render.assert_not_called()
    cast(Any, n.container_slot).update.assert_called()


def test_dead_resize_handle_stub_removed():
    from haybale_studio.skins.node_skin import NodeSkin

    assert not hasattr(NodeSkin, "_add_resize_handle")
