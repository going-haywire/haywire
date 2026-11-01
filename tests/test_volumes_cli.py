"""``haywire volumes`` — list, add, set, remove, reset."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from haywire.core.volumes import PROJECT_KEY, VolumeEntry, VolumeStore, set_volume_store

from haywire_studio.cli import volumescmd

pytestmark = pytest.mark.unit

MODELS = "haybale-models:volume:models"
SCANS = "user:volume:scans"


@pytest.fixture
def store(tmp_path):
    s = VolumeStore(tmp_path / "volumes.toml")
    set_volume_store(s)
    yield s
    set_volume_store(None)


def _run(argv):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    volumescmd.register(subparsers)
    args = parser.parse_args(argv)
    return args.handler(args)


def test_list_prints_key_label_location_and_missing(store, tmp_path, capsys):
    here = tmp_path / "here"
    here.mkdir()
    store.add(MODELS, label="Models", description="", location=tmp_path / "gone")
    store.add(SCANS, label="Scans", description="", location=here)

    assert _run(["volumes", "list"]) == 0
    lines = {ln.split()[0]: ln for ln in capsys.readouterr().out.splitlines()}

    assert set(lines) == {PROJECT_KEY, MODELS, SCANS}
    assert "Models" in lines[MODELS]
    assert str(tmp_path / "gone") in lines[MODELS]
    assert lines[MODELS].endswith("(missing)")
    assert "(missing)" not in lines[SCANS]
    for word in ("configured", "default", "fixed"):
        assert word not in "".join(lines.values())


def test_add_creates_a_user_volume(store, tmp_path, capsys):
    rc = _run(["volumes", "add", "scans", str(tmp_path), "--label", "Scans", "--description", "Drive"])
    assert rc == 0
    assert store.entry(SCANS) == VolumeEntry(SCANS, "Scans", "Drive", tmp_path)
    assert SCANS in capsys.readouterr().out


def test_add_makes_relative_absolute_without_creating(store, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _run(["volumes", "add", "scans", "rel"]) == 0
    assert store.entry(SCANS).location == Path.cwd() / "rel"
    assert store.entry(SCANS).label == "scans"
    assert not (tmp_path / "rel").exists()


def test_add_expands_home(store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert _run(["volumes", "add", "scans", "~/s"]) == 0
    assert store.entry(SCANS).location == tmp_path / "s"


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["volumes", "add", "Bad Name", "/x"], "Invalid volume name"),
        (["volumes", "add", "scans", "/x"], "already exists"),
    ],
)
def test_add_errors_go_to_stderr(store, tmp_path, capsys, argv, message):
    store.add(SCANS, label="Scans", description="", location=tmp_path)
    assert _run(argv) == 1
    assert message in capsys.readouterr().err


def test_set_changes_only_the_given_fields(store, tmp_path):
    store.add(MODELS, label="Models", description="Weights", location=tmp_path / "a")
    assert _run(["volumes", "set", MODELS, "--location", str(tmp_path / "b")]) == 0
    assert store.entry(MODELS) == VolumeEntry(MODELS, "Models", "Weights", tmp_path / "b")
    assert _run(["volumes", "set", MODELS, "--label", "My models", "--description", ""]) == 0
    assert store.entry(MODELS) == VolumeEntry(MODELS, "My models", "", tmp_path / "b")


def test_set_accepts_a_unique_name_part(store, tmp_path):
    store.add(MODELS, label="Models", description="", location=tmp_path / "a")
    assert _run(["volumes", "set", "models", "--location", str(tmp_path / "b")]) == 0
    assert store.entry(MODELS).location == tmp_path / "b"


def test_an_ambiguous_name_part_is_refused(store, tmp_path, capsys):
    store.add(MODELS, label="Models", description="", location=tmp_path)
    store.add("user:volume:models", label="Mine", description="", location=tmp_path)
    assert _run(["volumes", "set", "models", "--label", "x"]) == 1
    err = capsys.readouterr().err
    assert MODELS in err
    assert "user:volume:models" in err


def test_set_needs_at_least_one_option(store, tmp_path, capsys):
    store.add(MODELS, label="Models", description="", location=tmp_path)
    assert _run(["volumes", "set", MODELS]) == 1
    assert "nothing to change" in capsys.readouterr().err


@pytest.mark.parametrize("command", ["set", "remove"])
def test_project_is_refused(store, capsys, command):
    argv = ["volumes", command, PROJECT_KEY] + (["--label", "x"] if command == "set" else [])
    assert _run(argv) == 1
    assert "project" in capsys.readouterr().err


def test_set_relative_location_is_made_absolute(store, tmp_path, monkeypatch):
    store.add(MODELS, label="Models", description="", location=tmp_path)
    monkeypatch.chdir(tmp_path)
    assert _run(["volumes", "set", MODELS, "--location", "rel"]) == 0
    assert store.entry(MODELS).location == Path.cwd() / "rel"


def test_unknown_volume_is_refused(store, capsys):
    assert _run(["volumes", "set", "scans", "--label", "x"]) == 1
    assert "no volume" in capsys.readouterr().err
    assert _run(["volumes", "remove", "scans"]) == 1
    assert "no volume" in capsys.readouterr().err


def test_remove_deletes(store, tmp_path, capsys):
    store.add(SCANS, label="Scans", description="", location=tmp_path)
    assert _run(["volumes", "remove", "scans"]) == 0
    assert store.entry(SCANS) is None
    assert SCANS in capsys.readouterr().out


def test_remove_refuses_a_library_volume(store, tmp_path, capsys):
    store.ensure(MODELS, label="Models", description="", location=tmp_path)
    assert _run(["volumes", "remove", "models"]) == 1
    assert "reset" in capsys.readouterr().err
    assert store.entry(MODELS) is not None


def test_reset_writes_the_suggested_location_back(store, tmp_path, capsys):
    store.ensure(MODELS, label="Models", description="", location=tmp_path / "m")
    store.update(MODELS, location=tmp_path / "elsewhere")
    assert _run(["volumes", "reset", "models"]) == 0
    assert store.entry(MODELS).location == tmp_path / "m"
    assert f"{MODELS} -> {tmp_path / 'm'}" in capsys.readouterr().out
    store.add(SCANS, label="Scans", description="", location=tmp_path)
    assert _run(["volumes", "reset", "scans"]) == 1
    assert "user volume" in capsys.readouterr().err


def test_malformed_file_errors_on_stderr(store, tmp_path, capsys):
    store.path.write_text("[volumes\nbroken")
    assert _run(["volumes", "add", "scans", str(tmp_path)]) == 1
    assert "unreadable" in capsys.readouterr().err
    assert store.path.read_text() == "[volumes\nbroken"


def test_os_error_on_write_goes_to_stderr(store, tmp_path, capsys, monkeypatch):
    def boom(*_a, **_k):
        raise PermissionError("read-only drive")

    monkeypatch.setattr(VolumeStore, "add", boom)
    assert _run(["volumes", "add", "scans", str(tmp_path)]) == 1
    assert "read-only drive" in capsys.readouterr().err
