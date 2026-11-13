"""The Claude Code hooks in .claude/hooks/, run as Claude Code runs them, with a stand-in gh."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="the hooks need jq")


def _fake_bin(tmp_path: Path, gh_script: str | None) -> Path:
    """A bin folder holding jq and perl, and a stand-in gh running ``gh_script`` if given."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for tool in ("jq", "perl", "grep", "sed", "cat", "touch", "mkdir"):
        found = shutil.which(tool)
        if found and not (bin_dir / tool).exists():
            (bin_dir / tool).symlink_to(found)
    if gh_script is not None:
        gh = bin_dir / "gh"
        gh.write_text("#!/bin/bash\n" + gh_script)
        gh.chmod(0o755)
    return bin_dir


def _run(hook: str, payload: dict, bin_dir: Path, tmp_path: Path, **env: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(HOOKS / hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={"PATH": str(bin_dir), "TMPDIR": str(tmp_path), "CLAUDE_PROJECT_DIR": str(tmp_path), **env},
        check=False,
    )


# ── session-role.sh ─────────────────────────────────────────────────────────────────


def _role(tmp_path: Path, gh_script: str | None) -> str:
    result = _run("session-role.sh", {}, _fake_bin(tmp_path, gh_script), tmp_path)
    assert result.returncode == 0
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("permission", ["ADMIN", "MAINTAIN", "WRITE"])
def test_write_access_makes_a_maintainer(tmp_path, permission):
    assert _role(tmp_path, f"echo {permission}").startswith("Role: maintainer")


@pytest.mark.parametrize("permission", ["READ", "TRIAGE"])
def test_no_write_access_makes_a_contributor(tmp_path, permission):
    context = _role(tmp_path, f"echo {permission}")
    assert context.startswith(f"Role: contributor ({permission} access")
    assert "never merge or release" in context


def test_an_unanswered_check_makes_a_contributor(tmp_path):
    context = _role(tmp_path, "exit 1")
    assert context.startswith("Role: contributor (access could not be checked")


def test_a_missing_gh_makes_a_contributor_and_warns(tmp_path):
    context = _role(tmp_path, None)
    assert context.startswith("Role: contributor (access could not be checked")
    assert "GitHub CLI (gh) is not installed" in context


# ── guard-pr-merge.sh ───────────────────────────────────────────────────────────────

_GREEN = [
    {
        "__typename": "CheckRun",
        "workflowName": "CI",
        "name": "tests (macos-latest)",
        "status": "COMPLETED",
        "conclusion": "SUCCESS",
        "startedAt": "1",
    }
]
_GH_FOR_GUARD = 'if [ "$1" = "api" ]; then echo "$FAKE_THREADS"; else echo "$FAKE_VIEW"; fi'


def _merge(
    tmp_path: Path, *, draft=False, labels=(), threads=0, checks=_GREEN
) -> subprocess.CompletedProcess:
    view = {
        "isDraft": draft,
        "url": "https://github.com/o/r/pull/5",
        "labels": [{"name": name} for name in labels],
        "statusCheckRollup": list(checks),
    }
    payload = {"tool_input": {"command": "gh pr merge 5 --squash"}}
    bin_dir = _fake_bin(tmp_path, _GH_FOR_GUARD)
    return _run(
        "guard-pr-merge.sh",
        payload,
        bin_dir,
        tmp_path,
        FAKE_VIEW=json.dumps(view),
        FAKE_THREADS=str(threads),
    )


def test_a_ready_green_pr_merges(tmp_path):
    assert _merge(tmp_path).returncode == 0


@pytest.mark.parametrize("label", ["needs introduction", "agent files"])
def test_a_holding_label_blocks_the_merge(tmp_path, label):
    result = _merge(tmp_path, labels=["enhancement", label])
    assert result.returncode == 2
    assert label in result.stderr


def test_other_labels_do_not_hold_the_merge(tmp_path):
    assert _merge(tmp_path, labels=["enhancement", "introduction accepted"]).returncode == 0


def test_a_draft_blocks_the_merge(tmp_path):
    assert "draft" in _merge(tmp_path, draft=True).stderr


def test_an_unresolved_thread_blocks_the_merge(tmp_path):
    assert "unresolved" in _merge(tmp_path, threads=2).stderr


def test_a_missing_macos_check_blocks_the_merge(tmp_path):
    linux = [dict(_GREEN[0], name="tests (ubuntu-24.04)")]
    assert "macOS" in _merge(tmp_path, checks=linux).stderr


def test_other_commands_pass_the_guard(tmp_path):
    payload = {"tool_input": {"command": "gh pr view 5"}}
    result = _run("guard-pr-merge.sh", payload, _fake_bin(tmp_path, "exit 1"), tmp_path)
    assert result.returncode == 0


# ── require-workflow-skill.sh and mark-workflow-skill.sh ────────────────────────────


def _commit(tmp_path: Path, session: str) -> int:
    payload = {"session_id": session, "tool_input": {"command": "git commit -m x"}}
    return _run("require-workflow-skill.sh", payload, _fake_bin(tmp_path, None), tmp_path).returncode


def test_a_commit_waits_for_the_workflow_skill(tmp_path):
    assert _commit(tmp_path, "S1") == 2
    mark = {"session_id": "S1", "tool_input": {"skill": "haywire-workflow"}}
    _run("mark-workflow-skill.sh", mark, _fake_bin(tmp_path / "m", None), tmp_path)
    assert _commit(tmp_path, "S1") == 0
    assert _commit(tmp_path, "S2") == 2, "the mark is per session"


def test_typing_the_skill_command_counts_as_loading_it(tmp_path):
    mark = {"session_id": "S3", "prompt": "/haywire-workflow"}
    _run("mark-workflow-skill.sh", mark, _fake_bin(tmp_path / "m", None), tmp_path)
    assert _commit(tmp_path, "S3") == 0


def test_read_only_commands_need_no_skill(tmp_path):
    payload = {"session_id": "S4", "tool_input": {"command": "git status && gh pr view 5"}}
    assert _run("require-workflow-skill.sh", payload, _fake_bin(tmp_path, None), tmp_path).returncode == 0


def test_hooks_are_executable():
    for hook in HOOKS.glob("*.sh"):
        assert os.access(hook, os.X_OK), hook.name
