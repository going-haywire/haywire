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
_GH_FOR_GUARD = (
    'if [ "$1" = "api" ]; then echo "$FAKE_THREADS"; '
    'else echo "$*" > "$TMPDIR/gh-view-args"; echo "$FAKE_VIEW"; fi'
)
_CORE_URL = "https://github.com/going-haywire/haywire/pull/5"


def _merge(
    tmp_path: Path,
    *,
    draft=False,
    labels=(),
    threads=0,
    checks=_GREEN,
    url=_CORE_URL,
    command="gh pr merge 5 --squash",
) -> subprocess.CompletedProcess:
    view = {
        "isDraft": draft,
        "url": url,
        "labels": [{"name": name} for name in labels],
        "statusCheckRollup": list(checks),
    }
    payload = {"tool_input": {"command": command}}
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


def test_haywire_without_checks_blocks_the_merge(tmp_path):
    assert "no checks reported" in _merge(tmp_path, checks=[]).stderr


_LIBRARY_URL = "https://github.com/going-haywire/haybale-protokol/pull/4"


def test_the_guard_reads_the_pr_in_the_repo_named_by_repo(tmp_path):
    command = "gh pr merge 4 --repo going-haywire/haybale-protokol --squash --delete-branch"
    assert _merge(tmp_path, url=_LIBRARY_URL, command=command).returncode == 0
    args = (tmp_path / "gh-view-args").read_text().split()
    assert args[:3] == ["pr", "view", "4"]
    assert args[3:5] == ["--repo", "going-haywire/haybale-protokol"]


@pytest.mark.parametrize(
    "command",
    [
        "gh pr merge -R going-haywire/haybale-protokol 4 --squash",
        "gh pr merge --repo=going-haywire/haybale-protokol --squash 4",
        "gh pr merge --subject release 4 -R going-haywire/haybale-protokol",
    ],
)
def test_flag_values_are_never_read_as_the_pr(tmp_path, command):
    _merge(tmp_path, url=_LIBRARY_URL, command=command)
    args = (tmp_path / "gh-view-args").read_text().split()
    assert args[:3] == ["pr", "view", "4"]
    assert "going-haywire/haybale-protokol" in args


def test_a_library_without_ci_merges_without_checks(tmp_path):
    assert _merge(tmp_path, url=_LIBRARY_URL, checks=[]).returncode == 0


def test_a_library_still_needs_its_reported_checks_to_pass(tmp_path):
    failed = [dict(_GREEN[0], name="tests (ubuntu-24.04)", conclusion="FAILURE")]
    assert "checks not passed" in _merge(tmp_path, url=_LIBRARY_URL, checks=failed).stderr


def test_a_library_still_honours_the_holding_labels(tmp_path):
    assert _merge(tmp_path, url=_LIBRARY_URL, checks=[], labels=["agent files"]).returncode == 2


def test_other_commands_pass_the_guard(tmp_path):
    payload = {"tool_input": {"command": "gh pr view 5"}}
    result = _run("guard-pr-merge.sh", payload, _fake_bin(tmp_path, "exit 1"), tmp_path)
    assert result.returncode == 0


# ── block-dangerous-git.sh ──────────────────────────────────────────────────────────


def _blocked(tmp_path: Path, command: str) -> subprocess.CompletedProcess:
    payload = {"tool_input": {"command": command}}
    return _run("block-dangerous-git.sh", payload, _fake_bin(tmp_path, None), tmp_path)


@pytest.mark.parametrize(
    "command",
    [
        "gh api -X PUT repos/going-haywire/haywire/branches/master/protection --input p.json",
        "gh api --method DELETE repos/going-haywire/haywire/rulesets/12",
        "gh api --method=PATCH repos/going-haywire/haywire/rulesets/12",
        "gh api -XPOST repos/going-haywire/haywire/rulesets --input r.json",
        "gh api -x post repos/going-haywire/haywire/rulesets -f name=x",
        "gh api repos/going-haywire/haywire/rulesets -f name=x",
        "gh api repos/going-haywire/haywire/rulesets -F enabled=true",
        "gh api repos/going-haywire/haywire/branches/master/protection --input p.json",
        "gh api repos/going-haywire/haywire/rulesets --raw-field name=x",
        "gh api repos/going-haywire/haywire/rulesets -fname=x",
    ],
)
def test_gh_api_writes_to_rulesets_and_protection_are_blocked(tmp_path, command):
    result = _blocked(tmp_path, command)
    assert result.returncode == 2
    assert "rulesets or branch protection" in result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "gh api repos/going-haywire/haywire/rulesets",
        "gh api repos/going-haywire/haywire/rules/branches/master",
        "gh api -X GET repos/going-haywire/haywire/rulesets -f per_page=5",
        "gh api --method GET repos/going-haywire/haywire/branches/master/protection",
        "gh api repos/going-haywire/haywire/pulls/5/comments --jq '.[].body'",
        "gh api -X POST repos/going-haywire/haywire/issues -f title=x",
        "gh api -X DELETE repos/going-haywire/haywire/git/refs/heads/old",
    ],
)
def test_other_gh_api_calls_pass(tmp_path, command):
    assert _blocked(tmp_path, command).returncode == 0


@pytest.mark.parametrize(
    "command",
    ["git branch -D old", "git push --delete origin old", "git push origin :old", "git reset --hard"],
)
def test_the_existing_blocks_stay(tmp_path, command):
    assert _blocked(tmp_path, command).returncode == 2


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
