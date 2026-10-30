import sys

import pytest

from haywire.core.di import context
from haywire.core.volumes import (
    PROJECT_KEY,
    VolumeError,
    VolumeEscapeError,
    VolumePath,
    VolumeStore,
    VolumeUndefinedError,
    list_volumes,
    location_of,
    resolve,
)

pytestmark = pytest.mark.unit

V = "user:volume:v"


@pytest.fixture
def at(volume_store):
    """Put volume ``V`` at a location."""

    def _at(location):
        volume_store.add(V, label="v", description="", location=location)

    return _at


def test_stored_volume_resolves(tmp_path, volume_store):
    volume_store.add("user:volume:scans", label="Scans", description="", location=tmp_path / "s")
    assert location_of("user:volume:scans") == tmp_path / "s"


def test_project_is_the_workspace_root(tmp_path, workspace_root_restore):
    context.set_workspace_root(tmp_path / "ws")
    assert location_of(PROJECT_KEY) == tmp_path / "ws"


def test_project_undefined_without_workspace_root(workspace_root_restore):
    context._workspace_root = None
    with pytest.raises(VolumeUndefinedError):
        location_of(PROJECT_KEY)


def test_unknown_volume_raises():
    with pytest.raises(VolumeUndefinedError) as ei:
        location_of("user:volume:scans")
    assert ei.value.volume == "user:volume:scans"
    assert str(ei.value) == "volume 'user:volume:scans' is not defined on this machine"


def test_explicit_store_argument(tmp_path):
    other = VolumeStore(tmp_path / "other.toml")
    other.add("user:volume:scans", label="S", description="", location=tmp_path / "o")
    assert location_of("user:volume:scans", other) == tmp_path / "o"


def test_relative_joins_posix_parts(tmp_path, at):
    root = tmp_path / "root"
    at(root)
    assert resolve(VolumePath(V, "a/b/c.png")) == (root / "a" / "b" / "c.png").resolve()
    assert resolve(VolumePath(V, "")) == root.resolve()


def test_escape_by_dotdot_raises(tmp_path, at):
    root = tmp_path / "root"
    root.mkdir()
    at(root)
    for rel in ("../x", "a/../../x"):
        with pytest.raises(VolumeEscapeError):
            resolve(VolumePath(V, rel))
    assert resolve(VolumePath(V, "a/../b")) == (root / "b").resolve()


@pytest.mark.parametrize("rel", ["/etc/passwd", "C:\\x", "C:/x"])
def test_absolute_relative_raises(tmp_path, at, rel):
    at(tmp_path / "root")
    with pytest.raises(VolumeEscapeError) as ei:
        resolve(VolumePath(V, rel))
    assert ei.value.path == VolumePath(V, rel)


@pytest.mark.skipif(sys.platform == "win32", reason="backslash is a separator on Windows")
def test_backslash_is_literal_on_posix(tmp_path, at):
    root = tmp_path / "root"
    at(root)
    assert resolve(VolumePath(V, "sub\\file.png")) == (root / "sub\\file.png").resolve()


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_outward_symlink_raises(tmp_path, at):
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "outside").mkdir()
    (root / "link").symlink_to(tmp_path / "outside")
    at(root)
    with pytest.raises(VolumeEscapeError) as ei:
        resolve(VolumePath(V, "link/f.txt"))
    assert "link" in ei.value.reason


def test_missing_location_still_resolves(tmp_path, at):
    root = tmp_path / "nope"
    at(root)
    assert resolve(VolumePath(V, "a")) == (root / "a").resolve()
    assert not root.exists()


# ---- errors outside the escape/undefined cases stay VolumeErrors ----


def test_nul_byte_in_relative_is_an_escape(tmp_path, at):
    at(tmp_path)
    with pytest.raises(VolumeEscapeError) as ei:
        resolve(VolumePath(V, "a\0b"))
    assert "NUL" in ei.value.reason


def test_non_string_relative_is_an_escape(tmp_path, at):
    at(tmp_path)
    with pytest.raises(VolumeEscapeError) as ei:
        resolve(VolumePath(V, 5))  # type: ignore[arg-type]  # a hand-edited graph
    assert "not a string" in ei.value.reason


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlink_loop_is_a_volume_error(tmp_path, at):
    root = tmp_path / "root"
    root.mkdir()
    (root / "loop").symlink_to(root / "loop")
    at(root)
    with pytest.raises(VolumeError) as ei:
        resolve(VolumePath(V, "loop/x"))
    assert "cannot be resolved" in str(ei.value)


def test_list_volumes_reports_facts(tmp_path, volume_store, workspace_root_restore):
    context.set_workspace_root(tmp_path)
    (tmp_path / "here").mkdir()
    volume_store.add("user:volume:b", label="beta", description="d", location=tmp_path / "here")
    volume_store.add("user:volume:a", label="Alpha", description="", location=tmp_path / "gone")
    statuses = list_volumes()
    assert [s.key for s in statuses] == [PROJECT_KEY, "user:volume:a", "user:volume:b"]
    by = {s.key: s for s in statuses}
    assert (by[PROJECT_KEY].editable, by[PROJECT_KEY].exists) == (False, True)
    assert (by["user:volume:a"].editable, by["user:volume:a"].exists) == (True, False)
    assert (by["user:volume:b"].label, by["user:volume:b"].description) == ("beta", "d")
    assert not hasattr(by["user:volume:b"], "source")


def test_project_without_root_lists_without_location(workspace_root_restore):
    context._workspace_root = None
    (project,) = list_volumes()
    assert (project.location, project.exists) == (None, False)
