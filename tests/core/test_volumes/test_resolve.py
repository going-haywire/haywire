import sys
import pytest

from haywire.core.di import context
from haywire.core.volumes import (
    Volume,
    VolumeEscapeError,
    VolumePath,
    VolumeUndefinedError,
    list_volumes,
    location_of,
    resolve,
    set_volume_store,
)
from haywire.core.volumes.volume import ProjectVolume

pytestmark = pytest.mark.unit


def _declare(name, default=None, configurable=True):
    return type(
        f"V_{name}",
        (Volume,),
        {
            "name": name,
            "label": name.title(),
            "configurable": configurable,
            "default": classmethod(lambda cls: default),
        },
    )


def test_configured_beats_default(tmp_path, volume_store):
    _declare("scans", tmp_path / "default")
    volume_store.set("scans", tmp_path / "conf")
    assert location_of("scans") == tmp_path / "conf"


def test_default_used_when_unconfigured(tmp_path):
    _declare("scans", tmp_path / "default")
    assert location_of("scans") == tmp_path / "default"


def test_project_ignores_configuration(tmp_path, volume_store, workspace_root_restore):
    context.set_workspace_root(tmp_path / "ws")
    volume_store.path.write_text('[volumes]\nproject = "/x"\n')
    assert location_of("project") == tmp_path / "ws"


def test_project_undefined_without_workspace_root(workspace_root_restore):
    context._workspace_root = None
    assert ProjectVolume.default() is None
    with pytest.raises(VolumeUndefinedError):
        location_of("project")


def test_undeclared_configured_volume_resolves(tmp_path, volume_store):
    volume_store.set("scans", tmp_path / "s")
    assert location_of("scans") == tmp_path / "s"


def test_undefined_volume_raises():
    with pytest.raises(VolumeUndefinedError) as ei:
        location_of("scans")
    assert ei.value.volume == "scans"
    assert str(ei.value) == "volume 'scans' is not defined on this machine"


def test_explicit_store_argument(tmp_path):
    from haywire.core.volumes import VolumeStore

    other = VolumeStore(tmp_path / "other.toml")
    other.set("scans", tmp_path / "o")
    assert location_of("scans", other) == tmp_path / "o"


def test_relative_joins_posix_parts(tmp_path, volume_store):
    root = tmp_path / "root"
    volume_store.set("v", root)
    assert resolve(VolumePath("v", "a/b/c.png")) == (root / "a" / "b" / "c.png").resolve()
    assert resolve(VolumePath("v", "")) == root.resolve()


def test_escape_by_dotdot_raises(tmp_path, volume_store):
    root = tmp_path / "root"
    root.mkdir()
    volume_store.set("v", root)
    for rel in ("../x", "a/../../x"):
        with pytest.raises(VolumeEscapeError):
            resolve(VolumePath("v", rel))
    assert resolve(VolumePath("v", "a/../b")) == (root / "b").resolve()


@pytest.mark.parametrize("rel", ["/etc/passwd", "C:\\x", "C:/x"])
def test_absolute_relative_raises(tmp_path, volume_store, rel):
    volume_store.set("v", tmp_path / "root")
    with pytest.raises(VolumeEscapeError) as ei:
        resolve(VolumePath("v", rel))
    assert ei.value.path == VolumePath("v", rel)


@pytest.mark.skipif(sys.platform == "win32", reason="backslash is a separator on Windows")
def test_backslash_is_literal_on_posix(tmp_path, volume_store):
    root = tmp_path / "root"
    volume_store.set("v", root)
    assert resolve(VolumePath("v", "sub\\file.png")) == (root / "sub\\file.png").resolve()


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_outward_symlink_raises(tmp_path, volume_store):
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "outside").mkdir()
    (root / "link").symlink_to(tmp_path / "outside")
    volume_store.set("v", root)
    with pytest.raises(VolumeEscapeError) as ei:
        resolve(VolumePath("v", "link/f.txt"))
    assert "link" in ei.value.reason


def test_missing_location_still_resolves(tmp_path, volume_store):
    root = tmp_path / "nope"
    volume_store.set("v", root)
    assert resolve(VolumePath("v", "a")) == (root / "a").resolve()
    assert not root.exists()


def test_list_volumes_reports_sources(tmp_path, volume_store, workspace_root_restore):
    context.set_workspace_root(tmp_path)
    (tmp_path / "conf").mkdir()
    _declare("aaa_default", tmp_path / "d")
    _declare("zzz_none")
    _declare("mmm_conf", tmp_path / "unused")
    volume_store.set("mmm_conf", tmp_path / "conf")
    volume_store.set("extra", tmp_path / "nowhere")
    by = {s.name: s for s in list_volumes()}
    names = [s.name for s in list_volumes()]
    assert names[:2] == ["project", "home"]
    assert names[2:] == sorted(names[2:])

    def row(n):
        return (by[n].source, by[n].exists, by[n].declared, by[n].configurable)

    assert row("project") == ("fixed", True, True, False)
    assert row("aaa_default") == ("default", False, True, True)
    assert row("mmm_conf") == ("configured", True, True, True)
    assert row("zzz_none") == ("undefined", False, True, True)
    assert by["zzz_none"].location is None
    assert row("extra") == ("configured", False, False, True)
    assert by["extra"].label == "extra"


def test_store_swap_used_by_default(tmp_path, volume_store):
    volume_store.set("v", tmp_path)
    assert location_of("v") == tmp_path
    set_volume_store(None)
