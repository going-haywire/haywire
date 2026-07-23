import haywire.core.graph.editor  # noqa: F401  (circular-import guard)

from haywire.core.node.properties import NodeProperties


def _fresh_props() -> NodeProperties:
    # NodeProperties is a Settings bag; a bare instance carries descriptor
    # defaults (no registry / node needed for pure default reads).
    return NodeProperties()


def _values(d: dict) -> dict:
    # Settings.to_dict() is nested: {"values": {...}, "promoted": {...}}.
    return d.get("values", {})


def test_size_defaults_are_200():
    p = _fresh_props()
    assert p.width == 200.0
    assert p.height == 200.0


def test_size_adapt_defaults_to_auto():
    p = _fresh_props()
    assert p.size_adapt == "auto"


def test_size_adapt_accepts_all_four_modes():
    p = _fresh_props()
    for mode in ("auto", "manual_width", "manual_height", "manual"):
        p.size_adapt = mode
        assert p.size_adapt == mode


def test_default_props_serialize_sparse():
    # A default node emits nothing for size fields (sparse to_dict).
    p = _fresh_props()
    vals = _values(p.to_dict())
    assert "width" not in vals
    assert "height" not in vals
    assert "size_adapt" not in vals


def test_manual_size_round_trips():
    p = _fresh_props()
    p.size_adapt = "manual"
    p.width = 321.0
    out = p.to_dict()
    vals = _values(out)
    assert vals["size_adapt"] == "manual"
    assert vals["width"] == 321.0

    p2 = _fresh_props()
    p2.from_dict(out)
    assert p2.size_adapt == "manual"
    assert p2.width == 321.0


def test_width_min_height_min_removed():
    # These vestigial fields must be gone (never wired to anything).
    assert not hasattr(NodeProperties, "width_min")
    assert not hasattr(NodeProperties, "height_min")
