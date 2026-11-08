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

    lib_readme = tmp_path / "my-project" / "barn" / "hay-my-project" / "README.md"
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


@pytest.mark.unit
def test_init_writes_claude_md_with_release_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("my-project", auto_sync=False)

    project = tmp_path / "my-project"
    claude = (project / "CLAUDE.md").read_text()
    assert "## Releases" in claude
    assert "uv run --frozen haywire share --dry-run" in claude
    assert "share --first-release" in claude
    assert "publish.yml" in claude
    assert "publish-to-pypi.md" in claude

    agents = (project / "AGENTS.md").read_text()
    assert "CLAUDE.md" in agents


@pytest.mark.unit
def test_init_output_has_no_stale_save_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`haywire share --save` no longer exists: no scaffolded file or closing message may name it."""
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("my-project", auto_sync=False)

    project = tmp_path / "my-project"
    texts = {
        str(p.relative_to(project)): p.read_text()
        for p in (
            project / "README.md",
            project / "barn" / "hay-my-project" / "README.md",
            project / "CLAUDE.md",
        )
    }
    texts["<init output>"] = capsys.readouterr().out
    offenders = [where for where, text in texts.items() if "--save" in text]
    assert not offenders, f"stale --save in {offenders}"
