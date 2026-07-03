import haywire.core.graph.editor  # noqa: F401

import pytest


def test_id_encoding_deleted():
    import haywire.core.node.promotion as promo

    for name in ("encode_promoted_port_id", "decode_promoted_port_id", "is_promoted_port_id"):
        assert not hasattr(promo, name)


def test_port_id_decode_helpers_deleted():
    from haywire.core.types.port import DataPort

    assert not hasattr(DataPort, "_promoted_accessor")
    assert not hasattr(DataPort, "_promoted_descriptor_for")


@pytest.mark.integration
def test_resolve_promoted_matches_storage_key(make_node_with_setting):
    from haywire.core.node.promotion import _resolve_promoted, promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    promote_setting(node, "filter", "threshold")
    desc = type(node.filter).__dict__["threshold"]
    bag, resolved = _resolve_promoted(node, desc.storage_key)
    assert bag is node.filter
    assert resolved is desc


@pytest.mark.integration
def test_is_field_promoted(make_node_with_setting):
    from haywire.core.node.promotion import is_field_promoted, promote_setting

    node = make_node_with_setting(accessor="filter", field="threshold")
    assert is_field_promoted(node.filter, "threshold") is False
    promote_setting(node, "filter", "threshold")
    assert is_field_promoted(node.filter, "threshold") is True
