#!/usr/bin/env python3
"""Clean up after a merged pull request: the local branch, the remote branch and the worktree.

The only way agents delete branches: the hook blocks raw ``git branch -D`` and
``git push --delete``. ``finish`` deletes a branch only after it has found the
branch's pull request and seen it merged, and only when the local branch holds
nothing the pull request's head does not.

``finish <branch>``
    Refuses ``master``, ``main`` and ``gh-pages``. Refuses unless the pull request is
    ``MERGED``, or ``CLOSED`` with ``--abandon`` (the user's word), and refuses when
    the local branch has commits the pull request's head lacks. Inside the branch's
    worktree it detaches to ``<remote>/<default branch>``; from another folder it
    removes the branch's worktree if that is clean. Then it deletes the local branch,
    and the remote branch if it still exists. Running it again changes nothing.
``finish --sweep``
    Lists leftovers: local branches whose pull request merged or closed or whose
    upstream is gone, remote branches of finished pull requests, and detached clean
    worktrees. Acts only with ``--yes``; closed pull requests also need ``--abandon``.

Works in any GitHub repository of the organisation, core or a library. A maintainer's
clone has one remote, ``origin`` (the organisation's repository). A contributor's has
``upstream`` (the organisation's repository) and ``origin`` (the fork, which holds the
branches). The default branch is the one ``upstream`` or ``origin`` names as its HEAD.

Usage (standard library only; core also has it at ``scripts/finish.py``)::

    python3 finish.py fix/edge-drag
    python3 finish.py fix/old-idea --abandon
    python3 finish.py --sweep               # list only
    python3 finish.py --sweep --yes         # clean what is merged
    python3 finish.py --sweep --yes --abandon --json

Output is ``key: value`` lines on stdout, errors included (``error:`` then ``help:``).
Exit codes: 0 done or nothing to do, 1 refused or a command failed, 2 usage.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PROTECTED = frozenset({"master", "main", "gh-pages"})
DONE_STATES = frozenset({"MERGED", "CLOSED"})
PR_FIELDS = "number,state,url,headRefName,headRefOid,headRepositoryOwner"


class CommandFailed(Exception):
    """A git or gh command failed; its message says which and why."""


class Refused(Exception):
    """The branch may not be finished; carries what to do about it."""

    def __init__(self, message: str, help: str = "") -> None:
        super().__init__(message)
        self.help = help


@dataclass(frozen=True)
class Context:
    pr_remote: str
    """Remote of the organisation's repository: ``origin`` (maintainer) or ``upstream`` (contributor)."""
    branch_remote: str
    """Remote that holds the branches: always ``origin``."""
    pr_repo: str
    head_owner: str
    """Owner of ``branch_remote``: the pull request's head repository."""
    default_branch: str
    """The branch ``pr_remote`` names as its HEAD (``master``, ``main``)."""


@dataclass(frozen=True)
class Worktree:
    path: Path
    branch: str | None
    """Short branch name, or ``None`` for a detached checkout."""
    prunable: bool


# --- git and gh --------------------------------------------------------------


def run(*cmd: str, cwd: Path | None = None) -> str:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise CommandFailed(f"{cmd[0]} is not installed") from exc
    if proc.returncode != 0:
        raise CommandFailed(f"`{' '.join(cmd)}` failed: {proc.stderr.strip()}")
    return proc.stdout


def succeeds(*cmd: str, cwd: Path | None = None) -> bool:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, check=False).returncode == 0


def owner_and_repo(url: str) -> str:
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", url)
    if not match:
        raise CommandFailed(f"remote url {url!r} is not a GitHub repository")
    return match.group(1)


def detect_context() -> Context:
    remotes = run("git", "remote").split()
    if "origin" not in remotes:
        raise CommandFailed("this clone has no `origin` remote")
    pr_remote = "upstream" if "upstream" in remotes else "origin"
    return Context(
        pr_remote=pr_remote,
        branch_remote="origin",
        pr_repo=owner_and_repo(run("git", "config", "--get", f"remote.{pr_remote}.url").strip()),
        head_owner=owner_and_repo(run("git", "config", "--get", "remote.origin.url").strip()).split("/")[0],
        default_branch=default_branch(pr_remote),
    )


def default_branch(remote: str) -> str:
    """Return the branch *remote* names as its HEAD, from the clone's record or else the remote."""
    try:
        return run("git", "symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD").strip().split("/", 1)[1]
    except CommandFailed:
        pass
    # A clone made by `git remote add` has no record of the remote's HEAD.
    for line in run("git", "ls-remote", "--symref", remote, "HEAD").splitlines():
        if line.startswith("ref: refs/heads/"):
            return line.split()[1].removeprefix("refs/heads/")
    raise CommandFailed(f"cannot tell the default branch of `{remote}`")


def worktrees() -> list[Worktree]:
    """Return every worktree of the repository, the main folder first."""
    found: list[Worktree] = []
    for block in run("git", "worktree", "list", "--porcelain").strip().split("\n\n"):
        fields = dict(line.partition(" ")[::2] for line in block.splitlines())
        branch = fields.get("branch", "")
        found.append(
            Worktree(
                path=Path(fields["worktree"]).resolve(),
                branch=branch.removeprefix("refs/heads/") if branch else None,
                prunable="prunable" in fields,
            )
        )
    return found


def toplevel() -> Path:
    return Path(run("git", "rev-parse", "--show-toplevel").strip()).resolve()


def is_clean(path: Path) -> bool:
    return not run("git", "status", "--porcelain", cwd=path).strip()


def local_branches() -> dict[str, str]:
    """Return ``{branch: upstream track}``; the track reads ``[gone]`` when the upstream was deleted."""
    out = run("git", "for-each-ref", "refs/heads", "--format=%(refname:short)\t%(upstream:track)")
    return dict(line.split("\t") for line in out.splitlines())


def remote_branches(ctx: Context) -> dict[str, str]:
    """Return ``{branch: sha}`` of the heads on the branch remote."""
    out = run("git", "ls-remote", "--heads", ctx.branch_remote)
    return {
        ref.removeprefix("refs/heads/"): sha for sha, ref in (line.split("\t") for line in out.splitlines())
    }


def pull_requests(ctx: Context, branch: str | None = None) -> dict[str, dict]:
    """Return ``{head branch: newest pull request}`` from the head repository, via ``gh``."""
    cmd = ["gh", "pr", "list", "--repo", ctx.pr_repo, "--state", "all", "--limit", "1000"]
    cmd += ["--json", PR_FIELDS, *(["--head", branch] if branch else [])]
    newest: dict[str, dict] = {}
    for pr in json.loads(run(*cmd)):
        owner = (pr.get("headRepositoryOwner") or {}).get("login", "")
        if owner.lower() != ctx.head_owner.lower():
            continue
        if pr["number"] > newest.get(pr["headRefName"], {"number": 0})["number"]:
            newest[pr["headRefName"]] = pr
    return newest


# --- finishing one branch ----------------------------------------------------


def check_provable(ctx: Context, branch: str, pr: dict, abandon: bool, have_local: bool) -> None:
    """Raise ``Refused`` unless *pr* shows the branch is done and nothing local is lost."""
    state = pr["state"]
    if state == "OPEN":
        raise Refused(
            f"{pr['url']} is still open", "finish only follows a merge; merge or close the PR first"
        )
    if state == "CLOSED" and not abandon:
        raise Refused(
            f"{pr['url']} was closed without a merge",
            f"if the work is abandoned (the user's word), run: finish.py {branch} --abandon",
        )
    if not have_local:
        return
    head = pr["headRefOid"]
    if not succeeds("git", "cat-file", "-e", f"{head}^{{commit}}"):
        try:
            run("git", "fetch", "--quiet", ctx.pr_remote, f"refs/pull/{pr['number']}/head")
        except CommandFailed as exc:
            raise Refused(f"cannot compare {branch} with {pr['url']}: {exc}") from exc
    ahead = int(run("git", "rev-list", "--count", branch, f"^{head}").strip())
    if ahead:
        raise Refused(
            f"{branch} has {ahead} commit(s) the pull request's head lacks",
            f"push or save them first: git log {head[:9]}..{branch}",
        )


def finish_branch(ctx: Context, branch: str, abandon: bool, pr: dict | None = None) -> dict:
    """Finish *branch* and return what was done; raise ``Refused`` or ``CommandFailed``."""
    if branch in PROTECTED:
        raise Refused(f"{branch} is a permanent branch", "finish never touches master, main or gh-pages")
    have_local = succeeds("git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
    have_remote = branch in remote_branches(ctx)
    holder = next((w for w in worktrees() if w.branch == branch), None)
    result: dict = {"branch": branch, "actions": []}
    if not (have_local or have_remote or holder):
        result["note"] = "already finished: no local branch, remote branch or worktree (no-op)"
        return result
    pr = pr or pull_requests(ctx, branch).get(branch)
    if pr is None:
        raise Refused(
            f"no pull request found for {branch} in {ctx.pr_repo}",
            "finish needs the merged PR as proof; check the branch name",
        )
    check_provable(ctx, branch, pr, abandon, have_local)
    result["pr"] = f"#{pr['number']} {pr['state'].lower()} {pr['url']}"

    here, main = toplevel(), worktrees()[0].path
    if holder and not is_clean(holder.path):
        raise Refused(
            f"the worktree {holder.path} has uncommitted changes",
            "commit or discard them, then run finish again",
        )
    default, target = ctx.default_branch, f"{ctx.pr_remote}/{ctx.default_branch}"
    if holder and holder.path != here:
        run("git", "worktree", "remove", str(holder.path))
        result["actions"].append(f"removed worktree {holder.path}")
    elif holder:
        run("git", "fetch", "--quiet", ctx.pr_remote, default)
        if here == main:
            run("git", "switch", "--quiet", default)
            run("git", "merge", "--quiet", "--ff-only", target)
            result["actions"].append(f"switched the main folder to {default}")
        else:
            run("git", "switch", "--quiet", "--detach", target)
            result["actions"].append(f"detached {here} at {target}")
            result["help"] = (
                "this folder is now an empty detached checkout; remove it through your orchestrator "
                f"or with `git worktree remove {here}` from the main folder"
            )
    if have_local:
        run("git", "branch", "-D", branch)
        result["actions"].append("deleted local branch")
    if have_remote:
        run("git", "push", "--quiet", ctx.branch_remote, "--delete", branch)
        result["actions"].append(f"deleted {ctx.branch_remote}/{branch}")
    return result


# --- sweep -------------------------------------------------------------------


def sweep_rows(ctx: Context, abandon: bool) -> list[dict]:
    """Return one row per leftover, with a ``status`` of ``ready``, ``needs --abandon`` or ``skip: ...``."""
    prs = pull_requests(ctx)
    here = toplevel()
    rows: list[dict] = []

    def status_of(pr: dict) -> str:
        return "ready" if pr["state"] == "MERGED" or abandon else "needs --abandon"

    locals_ = local_branches()
    for branch, track in sorted(locals_.items()):
        if branch in PROTECTED:
            continue
        pr = prs.get(branch)
        if pr and pr["state"] in DONE_STATES:
            rows.append({"kind": "branch", "name": branch, "status": status_of(pr), "pr": pr})
        elif pr is None and track == "[gone]":
            rows.append(
                {"kind": "branch", "name": branch, "status": "skip: upstream gone, no PR to prove a merge"}
            )
    remotes = remote_branches(ctx)
    for branch, sha in sorted(remotes.items()):
        pr = prs.get(branch)
        if branch in PROTECTED or branch in locals_ or not pr or pr["state"] not in DONE_STATES:
            continue
        if sha != pr["headRefOid"]:
            rows.append(
                {"kind": "remote branch", "name": branch, "status": "skip: has commits after the PR's head"}
            )
        else:
            rows.append({"kind": "remote branch", "name": branch, "status": status_of(pr), "pr": pr})
    for tree in worktrees()[1:]:
        if tree.path != here and (tree.prunable or tree.branch is None):
            status = "ready" if tree.prunable or is_clean(tree.path) else "skip: not clean"
            rows.append({"kind": "worktree", "name": str(tree.path), "status": status})
    return rows


def apply_rows(ctx: Context, rows: list[dict], abandon: bool) -> None:
    """Act on every ``ready`` row; a failure is recorded on the row, not raised."""
    for row in rows:
        if row["status"] != "ready":
            continue
        try:
            if row["kind"] == "branch":
                finish_branch(ctx, row["name"], abandon, row["pr"])
            elif row["kind"] == "remote branch":
                run("git", "push", "--quiet", ctx.branch_remote, "--delete", row["name"])
            elif Path(row["name"]).exists():
                run("git", "worktree", "remove", row["name"])
            else:
                run("git", "worktree", "prune")
            row["status"] = "done"
        except (Refused, CommandFailed) as exc:
            row["status"] = f"failed: {exc}"


# --- output ------------------------------------------------------------------


def emit(fields: dict) -> None:
    for key, value in fields.items():
        if isinstance(value, list):
            print(f"{key}[{len(value)}]:")
            for item in value:
                print(f"  {item}")
        elif value is not None:
            print(f"{key}: {value}")


def error(message: str, help: str = "") -> int:
    emit({"error": message, "help": help or None})
    return 1


def print_sweep(rows: list[dict], applied: bool) -> None:
    if not rows:
        print("leftovers: 0 (nothing to clean up)")
        return
    print(f"leftovers[{len(rows)}]{{kind,name,status}}:")
    for row in rows:
        print(f"  {row['kind']},{row['name']},{row['status']}")
    if not applied:
        print("help: add --yes to clean the `ready` rows; closed PRs also need --abandon (the user's word)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("branch", nargs="?", help="the branch whose pull request merged")
    parser.add_argument("--abandon", action="store_true", help="also accept a closed, unmerged pull request")
    parser.add_argument(
        "--sweep", action="store_true", help="list leftovers instead of finishing one branch"
    )
    parser.add_argument("--yes", action="store_true", help="with --sweep: act on the ready rows")
    parser.add_argument("--json", action="store_true", help="one JSON object on stdout")
    args = parser.parse_args(argv)
    if args.sweep == bool(args.branch):
        parser.error("give a branch, or --sweep")
    if args.yes and not args.sweep:
        parser.error("--yes belongs to --sweep")

    try:
        ctx = detect_context()
        if args.sweep:
            rows = sweep_rows(ctx, args.abandon)
            if args.yes:
                apply_rows(ctx, rows, args.abandon)
            shown = [{k: v for k, v in row.items() if k != "pr"} for row in rows]
            if args.json:
                print(json.dumps({"leftovers": shown}, indent=2))
            else:
                print_sweep(shown, args.yes)
            return 0
        result = finish_branch(ctx, args.branch, args.abandon)
    except Refused as exc:
        return error(str(exc), exc.help)
    except CommandFailed as exc:
        return error(str(exc))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        emit({"finished": result["branch"], **{k: v for k, v in result.items() if k != "branch"}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
