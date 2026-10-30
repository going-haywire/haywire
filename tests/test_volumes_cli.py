"""``haywire volumes`` — list, set, remove."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from haywire.core.volumes import VolumeStore, set_volume_store

from haywire_studio.cli import volumescmd

pytestmark = pytest.mark.unit


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


def test_list_prints_one_line_per_volume(store, tmp_path, capsys):
    gone = tmp_path / "gone"
    here = tmp_path / "here"
    here.mkdir()
    store.set("models", gone)
    store.set("data", here)

    assert _run(["volumes", "list"]) == 0
    lines = {ln.split()[0]: ln for ln in capsys.readouterr().out.splitlines()}

    assert {"project", "home", "models", "data"} <= set(lines)
    assert "configured" in lines["models"]
    assert str(gone) in lines["models"]
    assert lines["models"].endswith("(missing)")
    assert "(missing)" not in lines["data"]
    assert "(missing)" not in lines["home"]


def test_set_absolute_writes_store(store, tmp_path, capsys):
    assert _run(["volumes", "set", "models", str(tmp_path / "m")]) == 0
    assert store.configured()["models"] == tmp_path / "m"


def test_set_makes_relative_absolute_without_creating(store, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _run(["volumes", "set", "models", "rel"]) == 0
    assert store.configured()["models"] == Path.cwd() / "rel"
    assert not (tmp_path / "rel").exists()


def test_set_expands_home(store, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert _run(["volumes", "set", "models", "~/m"]) == 0
    assert store.configured()["models"] == tmp_path / "m"


def test_set_project_refused(store, capsys):
    assert _run(["volumes", "set", "project", "/x"]) != 0
    assert "not configurable" in capsys.readouterr().err
    assert "project" not in store.configured()


def test_set_invalid_name_refused(store, capsys):
    assert _run(["volumes", "set", "Bad Name", "/x"]) != 0
    assert "Invalid volume name" in capsys.readouterr().err


def test_set_on_malformed_file_reports_without_traceback(store, capsys):
    store.path.write_text("[volumes\nbroken", encoding="utf-8")
    assert _run(["volumes", "set", "models", "/x"]) != 0
    assert capsys.readouterr().err.startswith("error:")


def test_remove_existing(store, tmp_path):
    store.set("models", tmp_path)
    assert _run(["volumes", "remove", "models"]) == 0
    assert "models" not in store.configured()


def test_remove_unknown_fails(store, capsys):
    assert _run(["volumes", "remove", "nope"]) != 0
    assert "nope" in capsys.readouterr().err
