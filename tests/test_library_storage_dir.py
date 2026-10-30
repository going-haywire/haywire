"""Tests for haywire.core.storage.library_storage_dir."""

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
