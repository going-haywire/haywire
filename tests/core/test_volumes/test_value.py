import dataclasses

import pytest

from haywire.core.volumes import VolumePath

pytestmark = pytest.mark.unit


def test_round_trip():
    v = VolumePath("models", "a/b.pth")
    assert VolumePath.from_dict(v.to_dict()) == v
    assert v.to_dict() == {"volume": "models", "relative": "a/b.pth"}


def test_from_empty_dict_defaults():
    assert VolumePath.from_dict({}) == VolumePath("project", "")


def test_str():
    assert str(VolumePath("models", "a/b.pth")) == "models:a/b.pth"


def test_frozen():
    v = VolumePath("x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        v.volume = "y"  # type: ignore[misc]
