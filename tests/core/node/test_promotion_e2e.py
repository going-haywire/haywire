"""End-to-end: promote a setting, wire an upstream outlet to the new inlet, confirm
the driven value reaches the setting read-tier, then demote and confirm fallback."""

import pytest

pytestmark = pytest.mark.integration


def test_full_promote_drive_demote_cycle(graph_with_library_system, library_system):
    from haywire.core.node.promotion import (
        demote_setting,
        promote_setting,
    )

    graph = graph_with_library_system

    # SettingsNode.example.example_float is a plain setting[FLOAT] (default 5 → clamped
    # to its 0..1 range is irrelevant here; we read the resolved default and the driven
    # value). MathOP.result is a FLOAT outlet we can drive.
    settings_wrapper = graph.create_node_wrapper("testing:node:SettingsNode", position=(0, 0))
    math_wrapper = graph.create_node_wrapper("example:node:MathOP", position=(200, 0))

    node = settings_wrapper.node
    default_value = node.example.example_float

    # 1. promote example.example_float -> inlet
    promote_setting(node, "example", "example_float")
    pid = type(node.example).__dict__["example_float"].storage_key
    assert pid in node.ports

    # 2. wire MathOP.result (FLOAT outlet) -> the promoted inlet
    edge = graph.create_edge_wrapper(math_wrapper.node_id, "result", settings_wrapper.node_id, pid)
    assert edge.state.is_valid()

    # 3. drive a value through the real edge and confirm the read-tier returns it
    math_wrapper.node.out("result", 0.875)
    node.ports[pid].resolve_dirty_data()
    assert node.example.example_float == 0.875  # port-driven, not the setting default

    # 4. demote; the inlet is gone. §C3 freeze-on-disconnect: the edge-driven
    #    value stays frozen in the cell (recovery is an explicit reset), so the
    #    setting keeps 0.875 rather than snapping back to its default.
    demote_setting(node, pid)
    assert pid not in node.ports
    assert node.example.example_float == 0.875

    # reset restores the resolved default (the recovery path).
    node.example.reset("example_float")
    assert node.example.example_float == default_value


def test_promoted_outlet_drives_consumer_lazily(graph_with_library_system, library_system):
    """A promoted OUTLET wired to a consumer inlet: a setting write (out of frame)
    fires on_changed → the outlet propagates lazily → the consumer pulls the fresh
    value on its next execution. The linked edge is forced is_lazy."""
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    graph = graph_with_library_system
    settings_wrapper = graph.create_node_wrapper("testing:node:SettingsNode", position=(0, 0))
    math_wrapper = graph.create_node_wrapper("example:node:MathOP", position=(200, 0))
    src = settings_wrapper.node

    # 1. promote example.example_float -> OUTLET
    promote_setting(src, "example", "example_float", direction=PortType.OUTLET)
    pid = type(src.example).__dict__["example_float"].storage_key
    assert src.ports[pid].is_outlet()
    assert src.ports[pid].is_linked_lazy is True

    # 2. wire the promoted outlet -> MathOP.value_a (FLOAT inlet)
    edge = graph.create_edge_wrapper(settings_wrapper.node_id, pid, math_wrapper.node_id, "value_a")
    assert edge.state.is_valid()
    # The linked edge was forced lazy by the is_linked_lazy outlet.
    assert edge.is_lazy is True

    consumer_inlet = math_wrapper.node.ports["value_a"]

    # 3. write the setting value OUT OF FRAME (widget-like). on_changed fires,
    #    the outlet propagates lazily → the consumer inlet is marked dirty.
    src.example.example_float = 0.625

    # 4. the consumer pulls the fresh value on its next execution frame.
    consumer_inlet.resolve_dirty_data()
    assert consumer_inlet.get_value() == 0.625


def test_promoted_inlet_does_not_subscribe_to_propagate(make_node_with_setting):
    """A promoted INLET has nothing downstream to drive, so bind_field must NOT
    install an on_changed→propagate handler on the shared cell."""
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold", direction=PortType.INLET)
    pid = type(node.filter).__dict__["threshold"].storage_key
    port = node.ports[pid]
    # The inlet's on_changed handler is not the outlet propagate handler.
    assert port._on_shared_field_changed not in port._data.on_changed


def test_demote_removes_outlet_propagate_subscription(make_node_with_setting):
    """demote/unbind_field removes the outlet's on_changed handler — no dangling
    handler left on the shared cell."""
    from haywire.core.node.promotion import (
        demote_setting,
        promote_setting,
    )
    from haywire.core.types.enums import PortType

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold", direction=PortType.OUTLET)
    pid = type(node.filter).__dict__["threshold"].storage_key
    port = node.ports[pid]
    desc = type(node.filter).__dict__["threshold"]
    cell = node.filter._cell_for(desc)
    assert port._on_shared_field_changed in cell.on_changed

    demote_setting(node, pid)
    # The handler is gone from the (surviving) setting cell.
    assert port._on_shared_field_changed not in cell.on_changed
