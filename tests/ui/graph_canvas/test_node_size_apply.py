import haywire.core.graph.editor  # noqa: F401  (circular-import guard)

from unittest.mock import MagicMock

from haybale_graph_editor.editors.graph_canvas.ui_node import UINode


def _ui_node_with_props(size_adapt: str, width: float, height: float) -> UINode:
    node = UINode.__new__(UINode)  # bypass __init__; we only exercise _apply_size
    node.wrapper = MagicMock()
    node.wrapper.node.props.size_adapt = size_adapt
    node.wrapper.node.props.width = width
    node.wrapper.node.props.height = height
    slot = MagicMock()
    slot._props = {}
    node.container_slot = slot
    return node


def _style_str(n: UINode) -> str:
    # _apply_size writes with replace= so the slot's inline style is authoritative.
    return n.container_slot.style.call_args.kwargs["replace"]


def test_apply_size_manual_writes_both_axes_as_minimums():
    n = _ui_node_with_props("manual", 300.0, 180.0)
    n._apply_size()
    style = _style_str(n)
    assert "min-width: 300" in style
    assert "min-height: 180" in style
    assert n.container_slot._props["data-size-adapt"] == "manual"
    n.container_slot.update.assert_called()


def test_apply_size_manual_width_writes_only_width_min():
    n = _ui_node_with_props("manual_width", 300.0, 180.0)
    n._apply_size()
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
        n._apply_size()
        style = _style_str(n)
        assert "overflow" not in style, f"{mode}: {style!r}"
        for decl in style.split(";"):
            prop = decl.split(":")[0].strip()
            assert prop not in ("width", "height"), f"{mode} wrote hard {prop}: {style!r}"


def test_apply_size_auto_clears_inline_size():
    n = _ui_node_with_props("auto", 300.0, 180.0)
    n._apply_size()
    style = _style_str(n)
    # auto axes carry no inline width/height (empty declarations)
    assert "width:" not in style
    assert "height:" not in style
    assert n.container_slot._props["data-size-adapt"] == "auto"


def test_size_change_restyles_slot_without_redraw():
    n = _ui_node_with_props("manual", 300.0, 180.0)
    n.render = MagicMock()  # spy: must NOT be called by a size change

    n.wrapper.node.props.width = 260.0
    n._on_size_field_change(260.0, 300.0)  # simulate a width change to 260

    n.render.assert_not_called()
    n.container_slot.update.assert_called()


def test_subscribe_size_fields_wires_three_fields():
    n = _ui_node_with_props("auto", 200.0, 200.0)
    n.wrapper.node.props.subscribe_field = MagicMock()
    n._subscribe_size_fields()
    watched = {call.args[0] for call in n.wrapper.node.props.subscribe_field.call_args_list}
    assert watched == {"width", "height", "size_adapt"}


def test_dead_resize_handle_stub_removed():
    from haybale_studio.skins.node_skin import NodeSkin

    assert not hasattr(NodeSkin, "_add_resize_handle")
