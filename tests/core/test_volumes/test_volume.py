from pathlib import Path

import pytest

from haywire.core.volumes import HomeVolume, ProjectVolume, Volume, all_volumes, volume_by_name
from haywire.core.di.context import set_workspace_root

pytestmark = pytest.mark.unit


def test_framework_volumes_registered():
    assert volume_by_name("project") is ProjectVolume
    assert volume_by_name("home") is HomeVolume
    assert {"project", "home"} <= {v.name for v in all_volumes()}
    assert ProjectVolume.configurable is False
    assert HomeVolume.default() == Path.home()


def test_project_default_follows_workspace_root(tmp_path, workspace_root_restore):
    set_workspace_root(tmp_path / "a")
    assert ProjectVolume.default() == tmp_path / "a"
    set_workspace_root(tmp_path / "b")
    assert ProjectVolume.default() == tmp_path / "b"
    assert ProjectVolume.default() == tmp_path / "b"


def test_invalid_name_raises():
    with pytest.raises(ValueError, match="Invalid"):

        class Bad(Volume):
            name = "Bad Name"
            label = "Bad"


def test_collision_raises():
    with pytest.raises(ValueError, match="collision"):

        class Other(Volume):
            __module__ = "somewhere.else"
            name = "project"
            label = "Other"

    assert volume_by_name("project") is ProjectVolume


def test_same_origin_supersedes():
    def declare():
        class Models(Volume):
            name = "models"
            label = "Models"

        return Models

    first, second = declare(), declare()
    assert first is not second
    assert volume_by_name("models") is second
