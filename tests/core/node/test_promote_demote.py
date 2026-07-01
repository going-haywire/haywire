import haywire.core.graph.editor  # noqa: F401

import pytest


@pytest.mark.integration
def test_promote_creates_inlet(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import encode_promoted_port_id, promote_setting

    promote_setting(node, "filter", "threshold")
    pid = encode_promoted_port_id("filter", "threshold")
    assert pid in node.ports
    assert node.ports[pid].is_inlet()


@pytest.mark.integration
def test_demote_removes_inlet(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import (
        demote_setting,
        encode_promoted_port_id,
        promote_setting,
    )

    promote_setting(node, "filter", "threshold")
    pid = encode_promoted_port_id("filter", "threshold")
    demote_setting(node, pid)
    assert pid not in node.ports


@pytest.mark.integration
def test_promote_is_idempotent(make_node_with_setting):
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import encode_promoted_port_id, promote_setting

    promote_setting(node, "filter", "threshold")
    promote_setting(node, "filter", "threshold")  # no-op, no raise
    pid = encode_promoted_port_id("filter", "threshold")
    assert pid in node.ports


@pytest.mark.integration
def test_promote_binding_is_the_port_id(make_node_with_setting):
    """The port id + DataPort.promoted are the whole binding signal — there is no
    descriptor flag (``_promoted_port_id`` retired, ADR 0014)."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    from haywire.core.node.promotion import (
        encode_promoted_port_id,
        is_field_promoted,
        promote_setting,
    )

    promote_setting(node, "filter", "threshold")
    pid = encode_promoted_port_id("filter", "threshold")
    assert pid in node.ports
    assert node.ports[pid].promoted is True
    assert is_field_promoted(node.filter, "threshold") is True
