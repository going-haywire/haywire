"""The adapters a project commits so every supported agent harness reaches its Farmhand bridge."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from haywire_studio.agents import BRIDGE_COMMAND, write_adapters


def test_the_claude_adapter_starts_the_bridge_and_allows_it(tmp_path: Path) -> None:
    write_adapters(tmp_path)
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
    write_adapters(tmp_path)
    write_adapters(tmp_path)
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert settings["permissions"]["allow"] == ["Bash(ls)", "mcp__farmhand"]
    assert settings["x"] == 1
    assert settings["enabledMcpjsonServers"] == ["farmhand"]
    assert set(json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]) == {"other", "farmhand"}


@pytest.mark.unit
def test_init_writes_the_adapters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("my-project", auto_sync=False)
    project = tmp_path / "my-project"
    assert "farmhand" in json.loads((project / ".mcp.json").read_text())["mcpServers"]
    assert "uv run haywire studio start" in (project / "CLAUDE.md").read_text()
