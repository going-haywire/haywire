"""scripts/tasks.py against temporary repositories with worktrees and stand-in gh and hc."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import tasks

pytestmark = pytest.mark.unit

SLUG_URL = "git@github.com:going-haywire/alpha.git"

GH = """#!{python}
import json, os, sys
if os.environ.get("GH_FAIL"):
    sys.exit("gh: no network")
if sys.argv[1:3] == ["pr", "list"]:
    head = sys.argv[sys.argv.index("--head") + 1]
    print(json.dumps(json.load(open(os.environ["GH_PRS"])).get(head, [])))
else:
    sys.exit("unexpected gh call: " + " ".join(sys.argv[1:]))
"""

HC = """#!{python}
import os, sys
if os.environ.get("HC_FAIL"):
    sys.exit(1)
print(open(os.environ["HC_LS"]).read())
"""

GREEN = [{"status": "COMPLETED", "conclusion": "SUCCESS"}]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def commit(cwd: Path, name: str) -> None:
    (cwd / name).write_text(name)
    git(cwd, "add", name)
    git(cwd, "commit", "-q", "-m", name)


class Folder:
    """A folder holding repository ``alpha`` (with a bare origin), a stand-in gh and a stand-in hc."""

    def __init__(self, tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = tmp / "repos"
        self.root.mkdir()
        self.prs_file = tmp / "prs.json"
        self.prs_file.write_text("{}")
        self.ls_file = tmp / "ls.json"
        self.ls_file.write_text(json.dumps({"terminals": []}))
        empty = tmp / "gitconfig"
        empty.write_text("")
        for key, value in {
            "GIT_CONFIG_GLOBAL": str(empty),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.org",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.org",
            "GH_PRS": str(self.prs_file),
            "HC_LS": str(self.ls_file),
        }.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("GH_FAIL", raising=False)
        monkeypatch.delenv("HC_FAIL", raising=False)
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        for name, script in {"gh": GH, "hc": HC}.items():
            tool = bin_dir / name
            tool.write_text(script.format(python=sys.executable))
            tool.chmod(0o755)
        monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
        origin = tmp / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "master", str(origin)], check=True)
        self.main = self.root / "alpha"
        subprocess.run(["git", "init", "-q", "-b", "master", str(self.main)], check=True)
        git(self.main, "remote", "add", "origin", SLUG_URL)
        git(self.main, "config", f"url.{origin}.insteadOf", SLUG_URL)
        commit(self.main, "base")
        git(self.main, "push", "-q", "origin", "master")

    def task(self, branch: str, push: bool = True, beside: bool = False) -> Path:
        """Add a worktree for a new *branch*, pushed unless told not to; return its folder."""
        parent = self.root if beside else self.root.parent / "trees"
        path = parent / branch.replace("/", "-")
        git(self.main, "worktree", "add", "-q", "-b", branch, str(path))
        commit(path, branch.replace("/", "_"))
        if push:
            git(path, "push", "-q", "-u", "origin", branch)
        return path.resolve()

    def pr(self, branch: str, number: int, state: str = "OPEN", draft: bool = False, **extra) -> None:
        prs = json.loads(self.prs_file.read_text())
        prs.setdefault(branch, []).append(
            {
                "number": number,
                "state": state,
                "isDraft": draft,
                "url": f"https://github.com/going-haywire/alpha/pull/{number}",
                "mergeable": "MERGEABLE",
                "statusCheckRollup": GREEN,
                **extra,
            }
        )
        self.prs_file.write_text(json.dumps(prs))

    def sessions(self, *terminals: dict) -> None:
        self.ls_file.write_text(json.dumps({"terminals": list(terminals)}))

    def lines(self, capsys: pytest.CaptureFixture) -> list[str]:
        assert tasks.main(["--root", str(self.root)]) == 0
        return capsys.readouterr().out.splitlines()


@pytest.fixture
def folder(tmp_path, monkeypatch) -> Folder:
    return Folder(tmp_path, monkeypatch)


def terminal(cwd: Path, address: str = "t1", status: str = "working", agent: str = "claude-code") -> dict:
    return {"address": address, "agent": agent, "cwd": str(cwd), "state": "live", "status": status}


def test_a_main_folder_on_master_is_not_a_task(folder, capsys):
    assert folder.lines(capsys) == [
        f"tasks: 0 (no worktree besides a main folder on its default branch under {folder.root.resolve()})"
    ]


def test_a_task_reads_as_one_line_with_its_pr_checks_and_agent(folder, capsys):
    path = folder.task("fix/edge-drag")
    folder.pr("fix/edge-drag", 141, draft=True)
    folder.sessions(terminal(path, "t1g"))
    assert folder.lines(capsys) == [
        "tasks[1]:",
        "  alpha / fix/edge-drag (t1g) · #141 draft · checks ✓ · working",
    ]


def test_a_task_without_a_pr_or_agent_says_so(folder, capsys):
    folder.task("feat/idea", push=False)
    assert folder.lines(capsys)[1] == "  alpha / feat/idea · no PR · not pushed"


def test_the_newest_pr_of_a_branch_is_the_one_shown(folder, capsys):
    folder.task("fix/again")
    folder.pr("fix/again", 7, state="CLOSED")
    folder.pr("fix/again", 9, state="MERGED")
    assert folder.lines(capsys)[1] == "  alpha / fix/again · #9 merged · checks ✓"


@pytest.mark.parametrize(
    ("rollup", "glyph"),
    [
        ([{"status": "COMPLETED", "conclusion": "FAILURE"}], "✗"),
        ([{"status": "IN_PROGRESS", "conclusion": ""}], "…"),
        (
            [
                {"status": "COMPLETED", "conclusion": "SUCCESS"},
                {"status": "COMPLETED", "conclusion": "SKIPPED"},
            ],
            "✓",
        ),
        ([{"__typename": "StatusContext", "state": "SUCCESS"}], "✓"),
    ],
)
def test_checks_collapse_to_one_glyph(folder, capsys, rollup, glyph):
    folder.task("fix/checks")
    folder.pr("fix/checks", 3, statusCheckRollup=rollup)
    assert f"checks {glyph}" in folder.lines(capsys)[1]


def test_a_pr_without_checks_shows_none(folder, capsys):
    folder.task("fix/quiet")
    folder.pr("fix/quiet", 3, statusCheckRollup=[])
    assert folder.lines(capsys)[1] == "  alpha / fix/quiet · #3 open"


def test_a_conflicting_pr_is_flagged(folder, capsys):
    folder.task("fix/clash")
    folder.pr("fix/clash", 4, mergeable="CONFLICTING")
    assert "conflicts" in folder.lines(capsys)[1]


def test_uncommitted_and_unpushed_work_is_flagged(folder, capsys):
    path = folder.task("fix/wip")
    commit(path, "more")
    (path / "base").write_text("changed")
    line = folder.lines(capsys)[1]
    assert line.endswith("· dirty · ahead 1")


def test_a_branch_behind_its_upstream_is_flagged(folder, capsys):
    path = folder.task("fix/behind")
    commit(path, "later")
    git(path, "push", "-q")
    git(path, "reset", "-q", "--hard", "HEAD~1")
    assert folder.lines(capsys)[1].endswith("· behind 1")


def test_gh_failing_reads_pr_unknown_not_an_error(folder, capsys, monkeypatch):
    folder.task("fix/offline")
    monkeypatch.setenv("GH_FAIL", "1")
    assert folder.lines(capsys)[1] == "  alpha / fix/offline · pr unknown"


def test_hc_failing_leaves_the_agent_out(folder, capsys, monkeypatch):
    path = folder.task("fix/solo")
    folder.sessions(terminal(path))
    monkeypatch.setenv("HC_FAIL", "1")
    assert "(t1)" not in folder.lines(capsys)[1]


def test_a_slot_that_fails_or_prints_no_json_adds_nothing(tmp_path):
    for name, body in {
        "broken": "import sys; sys.exit(1)",
        "chatty": "print('hello')",
        "good": "import json; print(json.dumps({'agents': [{'cwd': '/w', 'address': 'a1', 'status': ''}]}))",
    }.items():
        (tmp_path / name).mkdir()
        (tmp_path / name / "agents.py").write_text(body)
    assert tasks.agents(tmp_path) == {Path("/w").resolve(): {"cwd": "/w", "address": "a1", "status": ""}}


def test_plain_shells_and_other_folders_are_not_the_agent(folder, capsys):
    path = folder.task("fix/shell")
    folder.sessions(terminal(path, "t8", agent="zsh"), terminal(folder.main, "t9"))
    assert folder.lines(capsys)[1] == "  alpha / fix/shell · no PR"


def test_a_finished_detached_worktree_is_listed_as_empty(folder, capsys):
    path = folder.task("fix/done")
    git(path, "switch", "-q", "--detach", "origin/master")
    assert folder.lines(capsys)[1].startswith("  alpha / (detached, empty) ·")


def test_a_main_folder_on_a_branch_is_listed(folder, capsys):
    git(folder.main, "switch", "-q", "-c", "feat/in-main")
    assert folder.lines(capsys)[1].startswith("  alpha / feat/in-main")


def test_a_worktree_beside_the_repositories_is_not_a_repository_of_its_own(folder, capsys):
    folder.task("feat/beside", beside=True)
    (folder.root / "notes").mkdir()
    assert folder.lines(capsys)[0] == "tasks[1]:"


def test_json_carries_the_fields_the_line_leaves_out(folder, capsys):
    path = folder.task("fix/edge-drag")
    folder.pr("fix/edge-drag", 141, draft=True)
    folder.sessions(terminal(path, "t1g"))
    assert tasks.main(["--root", str(folder.root), "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["tasks"]
    assert row["repo"] == "alpha"
    assert row["branch"] == "fix/edge-drag"
    assert row["path"] == str(path)
    assert row["pr"]["url"].endswith("/pull/141")
    assert row["agent"] == {"address": "t1g", "status": "working"}
    assert row["dirty"] is False


def test_a_missing_root_is_an_error_with_a_help_line(folder, capsys):
    assert tasks.main(["--root", str(folder.root / "nowhere")]) == 1
    out = capsys.readouterr().out
    assert out.startswith("error:")
    assert "help:" in out
