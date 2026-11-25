"""Tests for haywire.core.storage: library_storage_dir and ensure_haywire_dir."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_returns_path_under_haywire_db(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from haywire.core.storage import library_storage_dir

    result = library_storage_dir("haybale_marketplace.config")
    assert result == tmp_path / ".haywire" / "db" / "haybale_marketplace"


@pytest.mark.unit
def test_normalises_to_top_level_package(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from haywire.core.storage import library_storage_dir

    result = library_storage_dir("haybale_foo.editors.bar")
    assert result == tmp_path / ".haywire" / "db" / "haybale_foo"


@pytest.mark.unit
def test_creates_directory_on_first_call(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from haywire.core.storage import library_storage_dir

    result = library_storage_dir("haybale_bar")
    assert result.is_dir()


@pytest.mark.unit
def test_idempotent_second_call(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from haywire.core.storage import library_storage_dir

    first = library_storage_dir("haybale_baz")
    second = library_storage_dir("haybale_baz")
    assert first == second
    assert second.is_dir()


@pytest.mark.unit
def test_bare_module_name_no_dot(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from haywire.core.storage import library_storage_dir

    result = library_storage_dir("haybale_qux")
    assert result == tmp_path / ".haywire" / "db" / "haybale_qux"


@pytest.mark.unit
def test_marketplace_storage_uses_module_name(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    from pathlib import Path

    from haywire.core.storage import library_storage_dir

    result = library_storage_dir("haybale_marketplace.config")
    assert str(result).endswith(str(Path(".haywire/db/haybale_marketplace")))
    assert not (tmp_path / ".haywire/db/haybale-marketplace").exists()


@pytest.mark.unit
def test_no_source_names_the_distribution_storage_dir():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    needle = "db/haybale-marketplace"
    hits = [
        str(p.relative_to(root))
        for top in ("packages", "barn")
        for p in (root / top).rglob("*.py")
        if needle in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert hits == []


@pytest.mark.unit
def test_haywire_dir_ignores_itself(tmp_path):
    from haywire.core.storage import ensure_haywire_dir

    directory = ensure_haywire_dir(tmp_path / "project" / ".haywire")

    assert directory.is_dir()
    assert (directory / ".gitignore").read_text() == "*\n"


@pytest.mark.unit
def test_haywire_dir_replaces_an_ignore_file_without_the_wildcard(tmp_path):
    from haywire.core.storage import ensure_haywire_dir

    directory = tmp_path / ".haywire"
    directory.mkdir()
    (directory / ".gitignore").write_text("studio.json\n")

    ensure_haywire_dir(directory)

    assert (directory / ".gitignore").read_text() == "*\n"


@pytest.mark.unit
def test_haywire_dir_keeps_an_ignore_file_that_holds_the_wildcard(tmp_path):
    from haywire.core.storage import ensure_haywire_dir

    directory = tmp_path / ".haywire"
    directory.mkdir()
    (directory / ".gitignore").write_text("# local\n*\n")

    ensure_haywire_dir(directory)

    assert (directory / ".gitignore").read_text() == "# local\n*\n"


@pytest.mark.unit
def test_another_folder_is_only_created(tmp_path):
    from haywire.core.storage import ensure_haywire_dir

    directory = ensure_haywire_dir(tmp_path / "settings")

    assert directory.is_dir()
    assert not (directory / ".gitignore").exists()


@pytest.mark.unit
def test_git_sees_nothing_in_the_folder(tmp_path):
    import subprocess

    from haywire.core.storage import ensure_haywire_dir

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (ensure_haywire_dir(tmp_path / ".haywire") / "settings.json").write_text("{}")

    status = subprocess.run(
        ["git", "status", "--porcelain", "-uall"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout
    assert status == ""
