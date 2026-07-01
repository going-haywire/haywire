import haywire.core.graph.editor  # noqa: F401

from haywire.core.node.promotion import (
    decode_promoted_port_id,
    encode_promoted_port_id,
    is_promoted_port_id,
)


def test_encode():
    assert encode_promoted_port_id("filter", "threshold") == "setting__filter__threshold"


def test_decode():
    assert decode_promoted_port_id("setting__filter__threshold") == ("filter", "threshold")


def test_is_promoted():
    assert is_promoted_port_id("setting__filter__threshold") is True
    assert is_promoted_port_id("regular_inlet") is False


def test_roundtrip():
    for acc, fld in [("filter", "threshold"), ("output", "scale")]:
        assert decode_promoted_port_id(encode_promoted_port_id(acc, fld)) == (acc, fld)


def test_metadata_to_port_kwargs_maps_names():
    """The descriptor's underscore attrs project onto the as_inlet kwarg names."""
    from haywire.barn.builtin.types import FLOAT
    from haywire.core.node.promotion import _metadata_to_port_kwargs
    from haywire.core.settings import NodeSettings, setting

    class bag(NodeSettings):
        x = setting[FLOAT](1.0, label="X", description="d")

    kwargs = _metadata_to_port_kwargs(bag.__dict__["x"])
    assert kwargs["label"] == "X"
    assert kwargs["description"] == "d"
    assert kwargs["type_cls"] is FLOAT


def test_metadata_label_falls_back_to_attr_name():
    """With no explicit label, the helper uses the field's attr name."""
    from haywire.barn.builtin.types import FLOAT
    from haywire.core.node.promotion import _metadata_to_port_kwargs
    from haywire.core.settings import NodeSettings, setting

    class bag(NodeSettings):
        threshold = setting[FLOAT](0.5)

    kwargs = _metadata_to_port_kwargs(bag.__dict__["threshold"])
    assert kwargs["label"] == "threshold"
