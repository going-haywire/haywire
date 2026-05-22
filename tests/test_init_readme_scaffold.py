"""haywire init scaffolds README.md with marker pairs — spec §6.6."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_init_writes_root_readme_with_marker_pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("my-project", auto_sync=False)

    readme = tmp_path / "my-project" / "README.md"
    assert readme.is_file()
    content = readme.read_text()
    assert "<!-- marketstall:share-url:start -->" in content
    assert "<!-- marketstall:share-url:end -->" in content
    assert "haywire share" in content  # placeholder mentions the command


@pytest.mark.unit
def test_init_writes_barn_library_readme_with_marker_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("my-project", auto_sync=False)

    lib_readme = tmp_path / "my-project" / "barn" / "haybale-my-project" / "README.md"
    assert lib_readme.is_file()
    content = lib_readme.read_text()
    assert "<!-- marketstall:share-url:start -->" in content
    assert "<!-- marketstall:share-url:end -->" in content


@pytest.mark.unit
def test_init_readme_mentions_project_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("my-project", auto_sync=False)

    readme = tmp_path / "my-project" / "README.md"
    assert "my-project" in readme.read_text() or "My Project" in readme.read_text()
