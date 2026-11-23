"""The agent files a repository commits: harness configs for a project, and an org library's files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from haywire_studio.agents import BRIDGE_COMMAND, CI_FILES, write_harness_configs, write_org_files


def test_the_claude_harness_config_starts_the_bridge_and_allows_it(tmp_path: Path) -> None:
    write_harness_configs(tmp_path)
    server = json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]["farmhand"]
    assert [server["command"], *server["args"]] == BRIDGE_COMMAND
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert settings["permissions"]["allow"] == ["mcp__farmhand"]
    assert settings["enabledMcpjsonServers"] == ["farmhand"]


def test_writing_again_keeps_the_project_s_own_settings_and_adds_nothing_twice(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(ls)"]}, "x": 1})
    )
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": {"command": "other"}}}))
    write_harness_configs(tmp_path)
    write_harness_configs(tmp_path)
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert settings["permissions"]["allow"] == ["Bash(ls)", "mcp__farmhand"]
    assert settings["x"] == 1
    assert settings["enabledMcpjsonServers"] == ["farmhand"]
    assert set(json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]) == {"other", "farmhand"}


@pytest.mark.unit
def test_init_writes_the_harness_configs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("my-project", auto_sync=False)
    project = tmp_path / "my-project"
    assert "farmhand" in json.loads((project / ".mcp.json").read_text())["mcpServers"]
    assert "uv run haywire studio start" in (project / "CLAUDE.md").read_text()


# -- an org library's files ------------------------------------------------------------

_CI = (
    "on:\n  push:\n    branches: [$default-branch]\n"
    "jobs:\n  ci:\n    uses: going-haywire/.github/.github/workflows/library-ci.yml@main\n"
)


def _fetch():
    return "abc123", {source: _CI for source in CI_FILES.values()}


def _library(tmp_path: Path) -> Path:
    library = tmp_path / "haybale-x"
    library.mkdir()
    (library / "pyproject.toml").write_text('[project]\nname = "haybale-x"\n')
    return library


def test_org_files_wire_core_s_hooks_from_the_clone_beside_it(tmp_path: Path) -> None:
    library = _library(tmp_path)
    write_org_files(library, fetch=_fetch)
    settings = json.loads((library / ".claude" / "settings.json").read_text())
    commands = [h["command"] for group in settings["hooks"]["PreToolUse"] for h in group["hooks"]]
    assert all(c.startswith('"$CLAUDE_PROJECT_DIR"/../haywire-repo/dev/hooks/') for c in commands)
    assert settings["permissions"]["allow"] == ["mcp__farmhand"]
    assert "farmhand" in json.loads((library / ".mcp.json").read_text())["mcpServers"]
    assert 'developer-docs = "../haywire-repo/docs"' in (library / "pyproject.toml").read_text()
    assert ".haywire/settings.json" in (library / ".gitignore").read_text()
    assert "worktree_setup.py" in (library / "t3.json").read_text()
    assert "## Working in this repository" in (library / "CLAUDE.md").read_text()


def test_the_ci_callers_are_pinned_and_name_the_library_s_branch(tmp_path: Path) -> None:
    library = _library(tmp_path)
    write_org_files(library, fetch=_fetch)
    ci = (library / ".github" / "workflows" / "ci.yml").read_text()
    assert "branches: [master]" in ci
    assert "library-ci.yml@abc123 # " in ci
    assert (library / ".github" / "dependabot.yml").is_file()


def test_existing_ci_files_stay_the_library_s_own(tmp_path: Path) -> None:
    library = _library(tmp_path)
    own = library / ".github" / "workflows" / "ci.yml"
    own.parent.mkdir(parents=True)
    own.write_text("own: true\n")
    calls: list[int] = []

    def counted():
        calls.append(1)
        return _fetch()

    write_org_files(library, fetch=counted)
    assert own.read_text() == "own: true\n"
    assert (library / ".github" / "workflows" / "nightly.yml").is_file()
    for target in CI_FILES:
        (library / target).parent.mkdir(parents=True, exist_ok=True)
        (library / target).touch()
    calls.clear()
    write_org_files(library, fetch=counted)
    assert calls == [], "nothing to fetch when every CI file is there"


def test_a_refresh_replaces_only_the_claude_md_block_and_changes_nothing_twice(tmp_path: Path) -> None:
    library = _library(tmp_path)
    (library / "CLAUDE.md").write_text(
        "# Lib\n\nIntro.\n\n## Working in this repository\n\nOld plugin text.\n\n## Releases\n\nKeep.\n"
    )
    write_org_files(library, fetch=_fetch)
    once = {p: p.read_text() for p in library.rglob("*") if p.is_file()}
    write_org_files(library, fetch=_fetch)
    twice = {p: p.read_text() for p in library.rglob("*") if p.is_file()}
    assert once == twice
    claude = (library / "CLAUDE.md").read_text()
    assert "Old plugin text" not in claude
    assert claude.startswith("# Lib\n\nIntro.\n")
    assert claude.count("## Working in this repository") == 1
    assert "## Releases\n\nKeep.\n" in claude


def test_a_refresh_drops_the_retired_plugin(tmp_path: Path) -> None:
    library = _library(tmp_path)
    (library / ".claude").mkdir()
    old = {"enabledPlugins": {"haywire-dev@going-haywire": False}, "extraKnownMarketplaces": {"x": {}}}
    (library / ".claude" / "settings.json").write_text(json.dumps(old))
    write_org_files(library, fetch=_fetch)
    settings = json.loads((library / ".claude" / "settings.json").read_text())
    assert "enabledPlugins" not in settings
    assert "extraKnownMarketplaces" not in settings
