import dataclasses

import pytest

from haywire.core.volumes import PROJECT_KEY, VolumePath

pytestmark = pytest.mark.unit


def test_round_trip():
    v = VolumePath("models", "a/b.pth")
    assert VolumePath.from_dict(v.to_dict()) == v
    assert v.to_dict() == {"volume": "models", "relative": "a/b.pth"}


def test_from_empty_dict_defaults():
    assert VolumePath.from_dict({}) == VolumePath(PROJECT_KEY, "")


def test_str():
    assert str(VolumePath("haybale-models:volume:models", "a/b.pth")) == "models:a/b.pth"


def test_frozen():
    v = VolumePath("x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.volume = "y"  # type: ignore[misc]


def test_base_round_trips_and_is_left_out_when_empty():
    v = VolumePath("models", "in/sub/b.pth", base="in")
    assert v.to_dict() == {"volume": "models", "relative": "in/sub/b.pth", "base": "in"}
    assert VolumePath.from_dict(v.to_dict()).base == "in"


def test_base_takes_no_part_in_equality():
    listed = VolumePath("models", "in/b.pth", base="in")
    assert listed == VolumePath("models", "in/b.pth")
    assert hash(listed) == hash(VolumePath("models", "in/b.pth"))


@pytest.mark.parametrize(
    ("relative", "base", "subpath"),
    [
        ("in/sub/b.pth", "in", "sub/b.pth"),
        ("in/b.pth", "in/", "b.pth"),
        ("in", "in", ""),
        ("in/b.pth", "", "in/b.pth"),
        ("inner/b.pth", "in", "inner/b.pth"),
        ("x/b.pth", "in", "x/b.pth"),
    ],
)
def test_subpath(relative, base, subpath):
    assert VolumePath("models", relative, base=base).subpath == subpath
