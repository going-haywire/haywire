import haywire.core.graph.editor  # noqa: F401

import pytest


@pytest.mark.integration
def test_promote_creates_inlet(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert pid in node.ports
    assert node.ports[pid].is_inlet()


@pytest.mark.integration
def test_demote_removes_inlet(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import (
        demote_setting,
        promote_setting,
    )

    promote_setting(node, "filter", "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key
    demote_setting(node, pid)
    assert pid not in node.ports


@pytest.mark.integration
def test_promote_is_idempotent(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import promote_setting

    promote_setting(node, "filter", "threshold")
    promote_setting(node, "filter", "threshold")  # no-op, no raise
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert pid in node.ports


@pytest.mark.integration
def test_promote_binding_is_the_port_id(make_node_with_setting):
    """The port id + DataPort.promoted are the whole binding signal — there is no
    descriptor flag (``_promoted_port_id`` retired, ADR 0014)."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import (
        is_field_promoted,
        promote_setting,
    )

    promote_setting(node, "filter", "threshold")
    pid = type(node.filter).__dict__["threshold"].storage_key
    assert pid in node.ports
    assert node.ports[pid].promoted is True
    assert is_field_promoted(node.filter, "threshold") is True


@pytest.mark.integration
def test_promoted_port_carries_the_settings_widget_config(library_system):
    """The promoted port's inline canvas widget (ui/skin/base.py, keyed off
    port.widget_key/widget_config) must render with the setting's own stamped
    widget contract (ADR 0017) — a CHOICES field's options, or a numeric
    field's min/max — not the IType's bare identity default with an empty
    widget_config. Regression test: _metadata_to_port_kwargs previously
    forwarded only label/description/order/type_cls, silently dropping every
    per-setting widget override onto promotion (predates the Tier-2 plan,
    caught during a later inspection of promotion.py)."""
    from unittest.mock import MagicMock

    from haywire.barn.builtin import widget_keys
    from haywire.barn.builtin.types import CHOICES, FLOAT
    from haywire.core.di.context import set_settings_registry, set_type_registry
    from haywire.core.node import BaseNode, node
    from haywire.core.node.promotion import promote_setting
    from haywire.core.settings import NodeSettings, setting

    set_type_registry(library_system.get_type_registry())
    set_settings_registry(library_system.get_settings_registry())

    class WidgetConfigBag(NodeSettings):
        threshold = setting[FLOAT](0.5, min=0.0, max=1.0)
        mode = setting[CHOICES]("fast", widget_config={"options": ["fast", "precise"]})

    node_cls = node(label="Widget Config Node")(
        type("_WidgetConfigNode", (BaseNode,), {"filter": WidgetConfigBag})
    )
    test_node = node_cls("widget-config-node", MagicMock())
    bag_cls = type(test_node.filter)

    promote_setting(test_node, "filter", "threshold")
    threshold_pid = bag_cls.__dict__["threshold"].storage_key
    threshold_port = test_node.ports[threshold_pid]
    assert threshold_port.widget_config["properties"]["min"] == 0.0
    assert threshold_port.widget_config["properties"]["max"] == 1.0

    promote_setting(test_node, "filter", "mode")
    mode_pid = bag_cls.__dict__["mode"].storage_key
    mode_port = test_node.ports[mode_pid]
    assert mode_port.widget_key == widget_keys.SELECT_WIDGET
    assert mode_port.widget_config["properties"]["options"] == ["fast", "precise"]
