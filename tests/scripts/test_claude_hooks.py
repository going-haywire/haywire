"""The Claude Code hooks of the haywire-dev plugin, run as Claude Code runs them, with a stand-in gh."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "plugins" / "haywire-dev" / "hooks"

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


def _role_in_clone(tmp_path: Path, remotes: dict[str, str]) -> tuple[str, str]:
    """Return the role text and the repository gh was asked about, in a clone with *remotes*."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for name, url in remotes.items():
        subprocess.run(["git", "-C", str(tmp_path), "remote", "add", name, url], check=True)
    bin_dir = _fake_bin(tmp_path / "b", 'echo "$3" > "$TMPDIR/gh-repo"; echo WRITE')
    git = shutil.which("git")
    assert git is not None
    (bin_dir / "git").symlink_to(git)
    result = _run("session-role.sh", {}, bin_dir, tmp_path)
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    return context, (tmp_path / "gh-repo").read_text().strip()


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:going-haywire/haybale-stream.git",
        "https://github.com/going-haywire/haybale-stream.git",
        "https://github.com/going-haywire/haybale-stream",
    ],
)
def test_a_library_clone_checks_its_own_repository(tmp_path, url):
    context, asked = _role_in_clone(tmp_path, {"origin": url})
    assert asked == "going-haywire/haybale-stream"
    assert "write access to going-haywire/haybale-stream" in context


def test_a_fork_checks_its_upstream(tmp_path):
    remotes = {
        "origin": "git@github.com:someone/haybale-stream.git",
        "upstream": "https://github.com/going-haywire/haybale-stream.git",
    }
    assert _role_in_clone(tmp_path, remotes)[1] == "going-haywire/haybale-stream"


def test_outside_a_clone_the_upstream_is_core(tmp_path):
    _role(tmp_path, 'echo "$3" > "$TMPDIR/gh-repo"; echo WRITE')
    assert (tmp_path / "gh-repo").read_text().strip() == "going-haywire/haywire"


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


# ── session-place.sh ────────────────────────────────────────────────────────────────

_HC = 'if [ "$1" = "get" ]; then echo "$FAKE_SELF"; else echo "$FAKE_LS"; fi'
_HERDR_APP = 'echo "$@" > "$TMPDIR/herdr-args"; exit "${HERDR_EXIT:-0}"'


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args], cwd=cwd, check=True
    )


def _place(
    tmp_path: Path,
    *,
    hc: bool = True,
    herdr: str | None = "ok",
    terminal: str | None = "t3g",
    main=False,
    live=(),
    where: str | None = "feat-x / 1",
    **extra_env: str,
) -> str:
    """The hook's context in ``tmp_path/work``: a main folder if ``main``, else a worktree on ``feat/x``.

    ``herdr`` is ``"ok"`` or ``"fail"`` for a stand-in herdr-app, ``None`` for none. Returns "" when the
    hook says nothing.
    """
    work = tmp_path / "work"
    if main:
        work.mkdir()
        _git(work, "init", "-q")
    else:
        origin = tmp_path / "origin"
        origin.mkdir()
        _git(origin, "init", "-q")
        _git(origin, "commit", "-q", "--allow-empty", "-m", "x")
        _git(origin, "worktree", "add", "-q", "-b", "feat/x", str(work))
    bin_dir = _fake_bin(tmp_path, None)
    (bin_dir / "git").symlink_to(shutil.which("git") or "git")
    for name, script, wanted in (("hc", _HC, hc), ("herdr-app", _HERDR_APP, herdr is not None)):
        if wanted:
            stand_in = bin_dir / name
            stand_in.write_text("#!/bin/bash\n" + script)
            stand_in.chmod(0o755)
    labels = {"herdr.tab": "tbABC", **({"where": where} if where else {})}
    env = {
        "CLAUDE_PROJECT_DIR": str(work.resolve()),
        "FAKE_SELF": json.dumps({"labels": labels}),
        "FAKE_LS": json.dumps({"terminals": list(live)}),
        "HERDR_EXIT": "1" if herdr == "fail" else "0",
    }
    if terminal:
        env["HC_TERMINAL_ID"] = terminal
    result = _run("session-place.sh", {}, bin_dir, tmp_path, **env, **extra_env)
    assert result.returncode == 0
    return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"] if result.stdout else ""


def _renamed(tmp_path: Path) -> str | None:
    """The arguments the stand-in herdr-app was called with, or ``None`` if it was not called."""
    args = tmp_path / "herdr-args"
    return args.read_text().strip() if args.exists() else None


def _session(address: str, cwd: Path, agent="claude-code", where="lead / 1") -> dict:
    return {"address": address, "agent": agent, "cwd": str(cwd.resolve()), "state": "live", "where": where}


def test_outside_herdr_the_place_hook_says_nothing(tmp_path):
    assert _place(tmp_path, terminal=None) == ""


def test_without_hc_the_place_hook_says_nothing(tmp_path):
    assert _place(tmp_path, hc=False) == ""


@pytest.mark.parametrize(
    "env", [{"CLAUDE_CODE_ENTRYPOINT": "t3-code", "T3CODE_THREAD_ID": "th-1"}, {"T3CODE_THREAD_ID": "th-1"}]
)
def test_in_t3_the_agent_learns_its_thread_and_how_to_message(tmp_path, env):
    context = _place(tmp_path, terminal=None, **env)
    assert context.startswith("You run in T3 Code as thread `th-1`.")
    assert "t3_thread_send" in context
    assert "orchestrators/t3.md" in context


def test_another_claude_code_entrypoint_is_not_t3(tmp_path):
    assert _place(tmp_path, terminal=None, CLAUDE_CODE_ENTRYPOINT="cli") == ""


def test_every_slot_that_speaks_is_heard(tmp_path):
    context = _place(tmp_path, CLAUDE_CODE_ENTRYPOINT="t3-code")
    assert "You run in herdr" in context
    assert "You run in T3 Code." in context


def test_in_herdr_the_agent_learns_its_place_and_how_to_message(tmp_path):
    context = _place(tmp_path)
    assert "`feat-x / 1` (`t3g`)" in context
    assert "hc send" in context
    assert "hc --skill" in context


def test_without_a_where_label_the_address_stands_alone(tmp_path):
    assert "You run in herdr as `t3g`. Other agents" in _place(tmp_path, where=None)


def test_an_unnamed_worktree_tab_is_renamed_to_the_branch(tmp_path):
    context = _place(tmp_path)
    assert _renamed(tmp_path) == "do tab.rename --id tbABC --name feat/x"
    assert "Your tab is now named `feat/x`." in context


@pytest.mark.parametrize("where", ["feat-x / my notes", "feat-x / feat/x"])
def test_a_tab_with_a_name_is_left_alone(tmp_path, where):
    context = _place(tmp_path, where=where)
    assert _renamed(tmp_path) is None
    assert "name your tab" not in context
    assert "now named" not in context


@pytest.mark.parametrize("herdr", ["fail", None])
def test_when_the_rename_cannot_run_the_agent_is_told_to(tmp_path, herdr):
    context = _place(tmp_path, herdr=herdr)
    assert "Before anything else, name your tab after your branch" in context
    assert "herdr-app do tab.rename --id tbABC --name feat/x" in context


def test_in_the_main_folder_the_agent_names_its_tab_by_role(tmp_path):
    context = _place(tmp_path, main=True)
    assert _renamed(tmp_path) is None
    assert "Before anything else, name your tab after your role" in context
    assert "herdr-app do tab.rename --id tbABC --name <role>" in context


def test_a_named_tab_in_the_main_folder_is_left_alone(tmp_path):
    assert "name your tab" not in _place(tmp_path, main=True, where="lead / lead")


def test_other_live_sessions_in_the_main_folder_are_warned_about(tmp_path):
    work = tmp_path / "work"
    live = [
        _session("t3g", work),
        _session("t9", work, where="haywire-repo / 1"),
        _session("t8", work, agent="zsh"),
        _session("t7", tmp_path / "elsewhere"),
    ]
    context = _place(tmp_path, main=True, live=live)
    assert "haywire-repo / 1 (t9)" in context
    assert "t8" not in context
    assert "t7" not in context
    assert "(t3g)" not in context.split("Warning")[1]


def test_a_worktree_gets_no_sharing_warning(tmp_path):
    live = [_session("t9", tmp_path / "work")]
    assert "Warning" not in _place(tmp_path, live=live)


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
    'else echo "$*" > "$TMPDIR/gh-view-args"; pwd -P > "$TMPDIR/gh-view-dir"; echo "$FAKE_VIEW"; fi'
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
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    view = {
        "isDraft": draft,
        "url": url,
        "labels": [{"name": name} for name in labels],
        "statusCheckRollup": list(checks),
    }
    payload: dict = {"tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = str(cwd)
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


def _gh_ran_in(tmp_path: Path) -> Path:
    return Path((tmp_path / "gh-view-dir").read_text().strip())


def test_the_guard_reads_the_pr_where_the_session_is(tmp_path):
    library = tmp_path / "haybale-protokol"
    library.mkdir()
    _merge(tmp_path, url=_LIBRARY_URL, command="gh pr merge 4 --squash", cwd=library)
    assert _gh_ran_in(tmp_path) == library.resolve()


@pytest.mark.parametrize(
    "command",
    [
        "cd haybale-protokol && gh pr merge 4 --squash",
        "cd elsewhere; cd 'haybale-protokol' && gh pr merge 4",
        "git fetch && cd {library} && gh pr merge 4 && cd ..",
    ],
)
def test_the_guard_follows_a_cd_before_the_merge(tmp_path, command):
    library = tmp_path / "haybale-protokol"
    library.mkdir()
    (tmp_path / "elsewhere").mkdir()
    _merge(tmp_path, url=_LIBRARY_URL, command=command.format(library=library), cwd=tmp_path)
    assert _gh_ran_in(tmp_path) == library.resolve()


def test_a_cd_the_guard_cannot_follow_blocks_the_merge(tmp_path):
    result = _merge(tmp_path, command="cd missing && gh pr merge 4", cwd=tmp_path)
    assert result.returncode == 2
    assert "--repo" in result.stderr


def test_an_org_library_without_checks_blocks_the_merge(tmp_path):
    assert "no checks reported" in _merge(tmp_path, url=_LIBRARY_URL, checks=[]).stderr


def test_an_org_library_needs_a_passed_macos_check(tmp_path):
    linux = [dict(_GREEN[0], name="ci / tests (ubuntu-24.04)")]
    assert "macOS" in _merge(tmp_path, url=_LIBRARY_URL, checks=linux).stderr


def test_a_repository_outside_the_rule_merges_without_checks(tmp_path):
    url = "https://github.com/going-haywire/.github/pull/2"
    assert _merge(tmp_path, url=url, checks=[]).returncode == 0


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


@pytest.mark.parametrize(
    "mark",
    [
        {"tool_input": {"skill": "haywire-dev:haywire-workflow"}},
        {"prompt": "/haywire-dev:haywire-workflow"},
    ],
)
def test_the_plugin_skill_name_counts_as_loading_it(tmp_path, mark):
    _run("mark-workflow-skill.sh", {"session_id": "P1", **mark}, _fake_bin(tmp_path / "m", None), tmp_path)
    assert _commit(tmp_path, "P1") == 0


def test_another_skill_does_not_count(tmp_path):
    mark = {"session_id": "P2", "tool_input": {"skill": "other:haywire-workflow-x"}}
    _run("mark-workflow-skill.sh", mark, _fake_bin(tmp_path / "m", None), tmp_path)
    assert _commit(tmp_path, "P2") == 2


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


# ── the plugin's wiring and core's ──────────────────────────────────────────────────


def _wiring(hooks: dict) -> set[tuple[str, str, str]]:
    """Return (event, matcher, script name) for every command hook."""
    return {
        (event, group.get("matcher", ""), hook["command"].rsplit("/", 1)[1])
        for event, groups in hooks.items()
        for group in groups
        for hook in group["hooks"]
        if "/hooks/" in hook["command"]
    }


def test_core_runs_the_same_plugin_hooks_as_a_library_session():
    plugin = json.loads((HOOKS / "hooks.json").read_text())["hooks"]
    core = json.loads((ROOT / ".claude" / "settings.json").read_text())["hooks"]
    assert _wiring(core) == _wiring(plugin)
    assert {name for _, _, name in _wiring(plugin)} == {hook.name for hook in HOOKS.glob("*.sh")}
    for groups in core.values():
        for group in groups:
            for hook in group["hooks"]:
                if "/hooks/" in hook["command"]:
                    assert '"$CLAUDE_PROJECT_DIR"/plugins/haywire-dev/hooks/' in hook["command"]


def test_core_reads_the_workflow_skill_from_the_plugin():
    link = ROOT / ".claude" / "skills" / "haywire-workflow"
    assert link.is_symlink()
    assert link.resolve() == (ROOT / "plugins" / "haywire-dev" / "skills" / "haywire-workflow").resolve()
