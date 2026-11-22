"""scripts/finish.py against a temporary repository with a bare remote, worktrees and a stand-in gh."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import finish

pytestmark = pytest.mark.unit

SLUG_URL = "git@github.com:going-haywire/haywire.git"

GH = """#!{python}
import os, sys
if sys.argv[1:3] == ["pr", "list"]:
    print(open(os.environ["GH_PRS"]).read())
else:
    sys.exit("unexpected gh call: " + " ".join(sys.argv[1:]))
"""


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def commit(cwd: Path, name: str) -> str:
    (cwd / name).write_text(name)
    git(cwd, "add", name)
    git(cwd, "commit", "-q", "-m", name)
    return git(cwd, "rev-parse", "HEAD")


class Repo:
    """A maintainer's clone: ``main`` (on *default*), ``origin`` (bare), a fake gh serving ``prs``."""

    def __init__(self, tmp: Path, monkeypatch: pytest.MonkeyPatch, default: str = "master") -> None:
        self.tmp = tmp
        self.default = default
        self.origin = tmp / "origin.git"
        self.main = tmp / "main"
        self.prs_file = tmp / "prs.json"
        self.prs_file.write_text("[]")
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
        }.items():
            monkeypatch.setenv(key, value)
        bin_dir = tmp / "bin"
        bin_dir.mkdir()
        gh = bin_dir / "gh"
        gh.write_text(GH.format(python=sys.executable))
        gh.chmod(0o755)
        monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
        subprocess.run(["git", "init", "-q", "--bare", "-b", default, str(self.origin)], check=True)
        subprocess.run(["git", "init", "-q", "-b", default, str(self.main)], check=True)
        git(self.main, "remote", "add", "origin", SLUG_URL)
        git(self.main, "config", f"url.{self.origin}.insteadOf", SLUG_URL)
        commit(self.main, "base")
        git(self.main, "push", "-q", "origin", default)
        monkeypatch.chdir(self.main)

    def branch(self, name: str, push: bool = True) -> str:
        """Create *name* with one commit, pushed unless told not to; return its head sha."""
        git(self.main, "switch", "-q", "-c", name)
        sha = commit(self.main, name.replace("/", "_"))
        if push:
            git(self.main, "push", "-q", "-u", "origin", name)
        git(self.main, "switch", "-q", self.default)
        return sha

    def worktree(self, branch: str) -> Path:
        path = self.tmp / "trees" / branch.replace("/", "-")
        git(self.main, "worktree", "add", "-q", str(path), branch)
        return path

    def pr(self, branch: str, sha: str, state: str = "MERGED", number: int = 1) -> None:
        prs = json.loads(self.prs_file.read_text())
        prs.append(
            {
                "number": number,
                "state": state,
                "url": f"https://github.com/going-haywire/haywire/pull/{number}",
                "headRefName": branch,
                "headRefOid": sha,
                "headRepositoryOwner": {"login": "going-haywire"},
            }
        )
        self.prs_file.write_text(json.dumps(prs))

    def local(self) -> set[str]:
        return set(git(self.main, "for-each-ref", "refs/heads", "--format=%(refname:short)").split())

    def remote(self) -> set[str]:
        return {
            line.split("refs/heads/")[1]
            for line in git(self.main, "ls-remote", "--heads", "origin").splitlines()
        }


@pytest.fixture
def repo(tmp_path, monkeypatch):
    return Repo(tmp_path, monkeypatch)


def test_a_merged_branch_loses_its_local_and_remote_branch(repo, capsys):
    sha = repo.branch("fix/edge")
    repo.pr("fix/edge", sha)
    assert finish.main(["fix/edge"]) == 0
    out = capsys.readouterr().out
    assert "finished: fix/edge" in out
    assert "deleted local branch" in out
    assert repo.local() == {"master"}
    assert repo.remote() == {"master"}


def test_finishing_twice_is_a_no_op(repo, capsys):
    sha = repo.branch("fix/edge")
    repo.pr("fix/edge", sha)
    finish.main(["fix/edge"])
    capsys.readouterr()
    assert finish.main(["fix/edge"]) == 0
    assert "no-op" in capsys.readouterr().out


def test_a_remote_branch_already_deleted_by_github_is_fine(repo):
    sha = repo.branch("fix/edge")
    repo.pr("fix/edge", sha)
    git(repo.main, "push", "-q", "origin", "--delete", "fix/edge")
    assert finish.main(["fix/edge"]) == 0
    assert repo.local() == {"master"}


@pytest.mark.parametrize("branch", ["master", "main", "gh-pages"])
def test_permanent_branches_are_refused(repo, capsys, branch):
    assert finish.main([branch]) == 1
    assert "permanent branch" in capsys.readouterr().out


def test_an_open_pr_is_refused(repo, capsys):
    sha = repo.branch("fix/edge")
    repo.pr("fix/edge", sha, state="OPEN")
    assert finish.main(["fix/edge"]) == 1
    assert "still open" in capsys.readouterr().out
    assert "fix/edge" in repo.local() | repo.remote()


def test_no_pr_is_refused(repo, capsys):
    repo.branch("fix/edge")
    assert finish.main(["fix/edge"]) == 1
    assert "no pull request found" in capsys.readouterr().out
    assert "fix/edge" in repo.local()


def test_a_closed_pr_needs_abandon(repo, capsys):
    sha = repo.branch("fix/idea")
    repo.pr("fix/idea", sha, state="CLOSED")
    assert finish.main(["fix/idea"]) == 1
    out = capsys.readouterr().out
    assert "closed without a merge" in out
    assert "--abandon" in out
    assert "fix/idea" in repo.local()
    assert finish.main(["fix/idea", "--abandon"]) == 0
    assert repo.local() == {"master"}
    assert repo.remote() == {"master"}


def test_a_pr_from_a_fork_with_the_same_branch_name_is_not_the_proof(repo, capsys):
    sha = repo.branch("fix/edge")
    repo.pr("fix/edge", sha)
    prs = json.loads(repo.prs_file.read_text())
    prs[0]["headRepositoryOwner"] = {"login": "someone-else"}
    repo.prs_file.write_text(json.dumps(prs))
    assert finish.main(["fix/edge"]) == 1
    assert "no pull request found" in capsys.readouterr().out


def test_unpushed_commits_are_refused(repo, capsys):
    sha = repo.branch("fix/edge")
    repo.pr("fix/edge", sha)
    git(repo.main, "switch", "-q", "fix/edge")
    commit(repo.main, "later")
    git(repo.main, "switch", "-q", "master")
    assert finish.main(["fix/edge"]) == 1
    assert "1 commit(s) found neither in the pull request's head nor on origin/master" in (
        capsys.readouterr().out
    )
    assert "fix/edge" in repo.local()
    assert "fix/edge" in repo.remote()


def test_a_branch_re_created_from_master_is_finished(repo, capsys):
    sha = repo.branch("fix/edge", push=False)
    repo.pr("fix/edge", sha)
    git(repo.main, "branch", "-q", "-D", "fix/edge")
    commit(repo.main, "other-pr")
    git(repo.main, "push", "-q", "origin", "master")
    git(repo.main, "branch", "-q", "fix/edge", "master")
    assert finish.main(["fix/edge"]) == 0
    assert "deleted local branch" in capsys.readouterr().out
    assert repo.local() == {"master"}


def test_a_re_created_branch_with_a_commit_found_nowhere_else_is_refused(repo, capsys):
    sha = repo.branch("fix/edge", push=False)
    repo.pr("fix/edge", sha)
    git(repo.main, "branch", "-q", "-D", "fix/edge")
    commit(repo.main, "other-pr")
    git(repo.main, "push", "-q", "origin", "master")
    git(repo.main, "switch", "-q", "-c", "fix/edge")
    commit(repo.main, "lost")
    git(repo.main, "switch", "-q", "master")
    assert finish.main(["fix/edge"]) == 1
    assert "1 commit(s) found neither" in capsys.readouterr().out
    assert "fix/edge" in repo.local()


def test_a_failed_fetch_of_the_default_branch_is_refused(repo, capsys, monkeypatch):
    sha = repo.branch("fix/edge")
    repo.pr("fix/edge", sha)
    real_run = finish.run

    def run(*cmd, cwd=None):
        if cmd[:2] == ("git", "fetch") and cmd[-1] == "master":
            raise finish.CommandFailed("`git fetch` failed: offline")
        return real_run(*cmd, cwd=cwd)

    monkeypatch.setattr(finish, "run", run)
    assert finish.main(["fix/edge"]) == 1
    assert "cannot compare fix/edge with origin/master" in capsys.readouterr().out
    assert "fix/edge" in repo.local()


def test_inside_its_worktree_the_folder_is_detached_at_master(repo, capsys, monkeypatch):
    sha = repo.branch("fix/edge")
    repo.pr("fix/edge", sha)
    tree = repo.worktree("fix/edge")
    monkeypatch.chdir(tree)
    assert finish.main(["fix/edge"]) == 0
    out = capsys.readouterr().out
    assert "empty detached checkout" in out
    assert git(tree, "branch", "--show-current") == ""
    assert git(tree, "rev-parse", "HEAD") == git(repo.main, "rev-parse", "origin/master")
    assert repo.local() == {"master"}
    assert repo.remote() == {"master"}


def test_from_the_main_folder_a_clean_worktree_is_removed(repo):
    sha = repo.branch("fix/edge")
    repo.pr("fix/edge", sha)
    tree = repo.worktree("fix/edge")
    assert finish.main(["fix/edge"]) == 0
    assert not tree.exists()
    assert repo.local() == {"master"}


def test_a_dirty_worktree_is_refused_and_kept(repo, capsys):
    sha = repo.branch("fix/edge")
    repo.pr("fix/edge", sha)
    tree = repo.worktree("fix/edge")
    (tree / "scratch.txt").write_text("wip")
    assert finish.main(["fix/edge"]) == 1
    assert "uncommitted changes" in capsys.readouterr().out
    assert tree.exists()
    assert "fix/edge" in repo.local()


def test_the_main_folder_returns_to_master(repo, monkeypatch):
    sha = repo.branch("fix/edge")
    repo.pr("fix/edge", sha)
    git(repo.main, "switch", "-q", "fix/edge")
    assert finish.main(["fix/edge"]) == 0
    assert git(repo.main, "branch", "--show-current") == "master"
    assert repo.local() == {"master"}


def test_a_repository_on_main_detaches_its_worktree_at_main(tmp_path, capsys, monkeypatch):
    repo = Repo(tmp_path, monkeypatch, default="main")
    sha = repo.branch("fix/edge")
    repo.pr("fix/edge", sha)
    tree = repo.worktree("fix/edge")
    monkeypatch.chdir(tree)
    assert finish.main(["fix/edge"]) == 0
    assert "at origin/main" in capsys.readouterr().out
    assert git(tree, "rev-parse", "HEAD") == git(repo.main, "rev-parse", "origin/main")
    assert repo.local() == {"main"}
    assert repo.remote() == {"main"}


def test_a_repository_on_main_returns_its_main_folder_to_main(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch, default="main")
    sha = repo.branch("fix/edge")
    repo.pr("fix/edge", sha)
    git(repo.main, "switch", "-q", "fix/edge")
    assert finish.main(["fix/edge"]) == 0
    assert git(repo.main, "branch", "--show-current") == "main"
    assert repo.local() == {"main"}


def test_the_default_branch_is_read_from_the_clone_record_first(repo):
    git(repo.main, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/master")
    assert finish.default_branch("origin") == "master"


def test_a_contributor_clone_reads_the_pr_upstream_and_deletes_on_the_fork(tmp_path, monkeypatch):
    repo = Repo(tmp_path, monkeypatch)
    git(repo.main, "remote", "add", "upstream", SLUG_URL)
    git(repo.main, "remote", "set-url", "origin", "git@github.com:someone/haywire.git")
    ctx = finish.detect_context()
    assert (ctx.pr_remote, ctx.branch_remote, ctx.pr_repo, ctx.head_owner) == (
        "upstream",
        "origin",
        "going-haywire/haywire",
        "someone",
    )


def test_unknown_flags_are_a_usage_error(repo):
    with pytest.raises(SystemExit) as exc:
        finish.main(["fix/edge", "--forse"])
    assert exc.value.code == 2


def test_a_branch_or_sweep_is_required(repo):
    with pytest.raises(SystemExit) as exc:
        finish.main([])
    assert exc.value.code == 2


# --- sweep -------------------------------------------------------------------


def _sweep_fixture(repo: Repo) -> None:
    repo.pr("fix/merged", repo.branch("fix/merged"), number=1)
    repo.pr("fix/closed", repo.branch("fix/closed"), state="CLOSED", number=2)
    repo.pr("fix/open", repo.branch("fix/open"), state="OPEN", number=3)
    repo.worktree("fix/open")


def test_sweep_lists_and_changes_nothing_without_yes(repo, capsys):
    _sweep_fixture(repo)
    assert finish.main(["--sweep", "--json"]) == 0
    rows = {row["name"]: row["status"] for row in json.loads(capsys.readouterr().out)["leftovers"]}
    assert rows == {"fix/merged": "ready", "fix/closed": "needs --abandon"}
    assert {"fix/merged", "fix/closed", "fix/open"} <= repo.local()


def test_sweep_yes_cleans_merged_and_keeps_closed_and_open(repo, capsys):
    _sweep_fixture(repo)
    assert finish.main(["--sweep", "--yes", "--json"]) == 0
    rows = {row["name"]: row["status"] for row in json.loads(capsys.readouterr().out)["leftovers"]}
    assert rows["fix/merged"] == "done"
    assert rows["fix/closed"] == "needs --abandon"
    assert repo.local() == {"master", "fix/closed", "fix/open"}
    assert repo.remote() == {"master", "fix/closed", "fix/open"}


def test_sweep_yes_abandon_also_cleans_closed(repo):
    _sweep_fixture(repo)
    assert finish.main(["--sweep", "--yes", "--abandon"]) == 0
    assert repo.local() == {"master", "fix/open"}


def test_sweep_lists_a_remote_only_branch_of_a_merged_pr(repo, capsys):
    sha = repo.branch("fix/remote-only")
    repo.pr("fix/remote-only", sha)
    git(repo.main, "branch", "-q", "-D", "fix/remote-only")
    finish.main(["--sweep", "--yes", "--json"])
    rows = json.loads(capsys.readouterr().out)["leftovers"]
    assert [(r["kind"], r["status"]) for r in rows] == [("remote branch", "done")]
    assert repo.remote() == {"master"}


def test_sweep_skips_a_remote_branch_with_commits_after_the_pr_head(repo, capsys):
    sha = repo.branch("fix/late")
    repo.pr("fix/late", sha)
    git(repo.main, "switch", "-q", "fix/late")
    commit(repo.main, "after")
    git(repo.main, "push", "-q", "origin", "fix/late")
    git(repo.main, "switch", "-q", "master")
    git(repo.main, "branch", "-q", "-D", "fix/late")
    finish.main(["--sweep", "--yes", "--json"])
    rows = json.loads(capsys.readouterr().out)["leftovers"]
    assert rows[0]["status"].startswith("skip: has commits after")
    assert "fix/late" in repo.remote()


def test_sweep_removes_a_detached_clean_worktree_and_keeps_a_dirty_one(repo, capsys):
    clean, dirty = repo.tmp / "trees" / "clean", repo.tmp / "trees" / "dirty"
    git(repo.main, "worktree", "add", "-q", "--detach", str(clean))
    git(repo.main, "worktree", "add", "-q", "--detach", str(dirty))
    (dirty / "wip.txt").write_text("wip")
    finish.main(["--sweep", "--yes", "--json"])
    rows = {Path(r["name"]).name: r["status"] for r in json.loads(capsys.readouterr().out)["leftovers"]}
    assert rows == {"clean": "done", "dirty": "skip: not clean"}
    assert not clean.exists()
    assert dirty.exists()


def test_sweep_never_acts_on_a_gone_upstream_without_a_pr(repo, capsys):
    repo.branch("fix/mystery")
    git(repo.main, "push", "-q", "origin", "--delete", "fix/mystery")
    git(repo.main, "fetch", "-q", "--prune", "origin")
    finish.main(["--sweep", "--yes", "--json"])
    rows = json.loads(capsys.readouterr().out)["leftovers"]
    assert rows[0]["status"].startswith("skip: upstream gone")
    assert "fix/mystery" in repo.local()


def test_sweep_with_nothing_to_do_says_so(repo, capsys):
    assert finish.main(["--sweep"]) == 0
    assert "leftovers: 0" in capsys.readouterr().out
