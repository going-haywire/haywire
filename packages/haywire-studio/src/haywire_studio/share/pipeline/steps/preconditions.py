"""Step 1 — the combined precondition gate."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from haywire_studio.share.git import git, git_remote
from haywire_studio.share.manifest.errors import InvalidOsDeclarationError, ManifestReadError
from haywire_studio.share.manifest.os_field import describe_os_fix, invalid_os_values
from haywire_studio.share.manifest.reader import read_manifest
from haywire_studio.share.pipeline.results import PreconditionFailure, PreconditionsReport

if TYPE_CHECKING:
    from haywire_studio.share.pipeline.pipeline import SharePipeline

GIT_INSTALL_HINT = (
    "macOS (Homebrew):  brew install git\n"
    "Ubuntu/Debian:     sudo apt-get install git\n"
    "Windows:           https://git-scm.com/download/win"
)

_NO_REMOTE_HINT = "git remote add origin <your-repo-url>\ngit push -u origin <branch-name>"


def check(pipeline: "SharePipeline") -> PreconditionsReport:
    """Verify everything needed to publish, collecting ALL failures.

    Reports rather than raises so the wizard's first panel can explain why
    a workspace cannot be shared. The menu item is always enabled — a
    disabled one cannot carry a tooltip, since the design guide's disabled
    state includes ``pointer-events: none`` (design-guide.md:725).

    The remote reachability check is ``git ls-remote --symref origin
    HEAD``: it exercises the exact credential path ``git push`` uses, so
    an auth failure surfaces here rather than after a commit and tag
    already exist. ``--symref`` narrows the round-trip to one ref instead
    of every ref, and its output additionally names the remote's default
    branch (``ref: refs/heads/<name>\\tHEAD``), which the non-default-
    branch check below needs. ``git symbolic-ref refs/remotes/origin/HEAD``
    is NOT a usable local substitute for that — it is unset in this very
    repo (nothing populates it without an explicit ``git remote set-head``)
    — so the remote round-trip is the only reliable source.

    Every ``barn/*`` library's ``pyproject.toml`` is parsed with
    :func:`read_manifest`; a malformed file or an invalid ``os``
    declaration is reported here rather than surfacing later as a crash
    mid-docs-generation or a silently wrong marketstall entry.

    The detached-HEAD and non-default-branch checks below always run —
    there is no way to bypass them.
    """
    failures: list[PreconditionFailure] = []
    remote_url: str | None = None
    default_branch: str | None = None

    version = git(["--version"], cwd=pipeline.repo_root, timeout=10.0)
    if not version.ok:
        # Nothing else is checkable without git — every remaining probe
        # would report the same missing binary as a different symptom.
        return PreconditionsReport(
            failures=[PreconditionFailure(message="git is not installed.", remedy=GIT_INSTALL_HINT)],
            remote_url=None,
            barn_libraries=[],
        )

    barn = pipeline.repo_root / "barn"
    barn_libraries: list[Path] = []
    if not barn.is_dir():
        failures.append(
            PreconditionFailure(
                message=f"No barn/ directory at {pipeline.repo_root}. Is this a haywire project root?",
                remedy=(
                    "Run this from your haywire project root (the directory containing "
                    "barn/), or run `haywire init <name>` to scaffold a new project."
                ),
            )
        )
    else:
        barn_libraries = pipeline._barn_library_dirs()
        if not barn_libraries:
            failures.append(
                PreconditionFailure(
                    message=f"No library with a pyproject.toml under {barn}. Nothing to publish.",
                    remedy=(
                        "Add a library under barn/, each with its own pyproject.toml — "
                        "see docs/haybale/haybale-package-canon.md for the expected layout."
                    ),
                )
            )

    for lib_dir in barn_libraries:
        pyproject_path = lib_dir / "pyproject.toml"
        try:
            rel_path = pyproject_path.relative_to(pipeline.repo_root)
        except ValueError:
            rel_path = pyproject_path
        try:
            rel_lib_dir = lib_dir.relative_to(pipeline.repo_root)
        except ValueError:
            rel_lib_dir = lib_dir
        try:
            read_manifest(lib_dir)
        except InvalidOsDeclarationError as exc:
            # invalid_os_values() re-reads the raw list to compute what
            # the fix would actually do — read_manifest() above already
            # proved the TOML parses (only validation failed), so this
            # read cannot legitimately raise ManifestReadError here.
            invalid_values = invalid_os_values(lib_dir)
            failures.append(
                PreconditionFailure(
                    message=f"Invalid manifest at {rel_path}: {exc}",
                    remedy=(
                        "[tool.haywire].os may only declare `macos`, `windows`, `linux`. "
                        "`other` is a runtime sentinel for platforms that don't map to one "
                        "of those three — it is set at runtime and must never be declared. "
                        "Remove it (or the whole invalid entry) from the list."
                    ),
                    fix_id="strip_os",
                    fix_label=describe_os_fix(invalid_values),
                    lib_dir=str(rel_lib_dir),
                )
            )
        except ManifestReadError as exc:
            failures.append(
                PreconditionFailure(
                    message=f"Could not read {rel_path}: {exc}",
                    remedy=f"Fix the TOML in {rel_path} so it parses, then try again.",
                )
            )

    remote = git(["remote", "get-url", "origin"], cwd=pipeline.repo_root, timeout=10.0)
    if not remote.ok or not remote.stdout.strip():
        failures.append(
            PreconditionFailure(
                message="No 'origin' remote is configured.",
                remedy=_NO_REMOTE_HINT,
                fix_id="add_origin",
                fix_label="Add origin remote",
            )
        )
    else:
        remote_url = remote.stdout.strip()
        reachable = git_remote(
            ["ls-remote", "--symref", "origin", "HEAD"], cwd=pipeline.repo_root, timeout=60.0
        )
        if not reachable.ok:
            detail = (reachable.stderr or reachable.stdout).strip().splitlines()
            first = detail[0] if detail else f"exit {reachable.returncode}"
            failures.append(
                PreconditionFailure(
                    message=f"Cannot reach origin ({remote_url}): {first}",
                    remedy="Check the URL and your credentials, then try again.",
                )
            )
        else:
            # Absent when the remote has never had anything pushed to it
            # (an empty repo has no HEAD to symref) — that is "nothing has
            # ever been shared", not a failure, so default_branch simply
            # stays None and the non-default-branch check below is skipped.
            for line in reachable.stdout.splitlines():
                left, sep, right = line.partition("\t")
                if sep and right.strip() == "HEAD" and left.startswith("ref: refs/heads/"):
                    default_branch = left.removeprefix("ref: refs/heads/").strip()
                    break

    symbolic = git(["symbolic-ref", "-q", "HEAD"], cwd=pipeline.repo_root, timeout=10.0)
    if not symbolic.ok:
        # Genuinely detached: HEAD points straight at a commit rather
        # than a branch ref. `current_branch() == "HEAD"` alone is NOT
        # this test — an unborn branch (a fresh repo before its first
        # commit) prints the same literal "HEAD" from `rev-parse
        # --abbrev-ref HEAD` while `symbolic-ref` still succeeds, so
        # relying on that string would misreport a brand-new project.
        failures.append(
            PreconditionFailure(
                message="HEAD is detached — no branch is currently checked out.",
                remedy=_detached_head_remedy(pipeline),
            )
        )
    elif default_branch is not None:
        # symbolic.ok already proved HEAD is not detached (above), so
        # current_branch() cannot legitimately return None here — but it
        # is a general-purpose query, not a private helper, so the None
        # case is still handled explicitly rather than assumed away.
        current = pipeline.current_branch()
        if current is None:
            failures.append(
                PreconditionFailure(
                    message="HEAD is detached — no branch is currently checked out.",
                    remedy=_detached_head_remedy(pipeline),
                )
            )
        elif current != default_branch:
            failures.append(
                PreconditionFailure(
                    message=(
                        f"Currently on `{current}`, but the repository's default branch "
                        f"is `{default_branch}`."
                    ),
                    remedy=(
                        f"Switch to the default branch and publish from there: "
                        f"`git switch {default_branch}`."
                    ),
                )
            )

    if not failures:
        pipeline.remote_url = remote_url

    return PreconditionsReport(
        failures=failures,
        remote_url=remote_url,
        barn_libraries=barn_libraries,
        default_branch=default_branch,
    )


def _detached_head_remedy(pipeline: "SharePipeline") -> str:
    """Remedy text for a detached HEAD, computed from ``git branch --contains HEAD``.

    Each line is prefixed ``"* "`` (current) or ``"  "`` (other); a
    detached HEAD also shows a synthetic ``(HEAD detached at <sha>)`` /
    ``(HEAD detached from <sha>)`` line, which is not a real branch name
    and is filtered out. If no real branch remains — a dangling commit no
    branch was ever built from — the remedy falls back to naming a new
    one.
    """
    result = git(["branch", "--contains", "HEAD"], cwd=pipeline.repo_root, timeout=10.0)
    names = []
    for line in result.stdout.splitlines():
        name = line[2:].strip() if len(line) >= 2 else line.strip()
        if not name or name.startswith("(HEAD detached"):
            continue
        names.append(name)

    if names:
        quoted = ", ".join(f"`{n}`" for n in names)
        return f"This commit is on {quoted} — run `git switch {names[0]}`."
    return (
        "This commit is not on any branch — run `git switch -c my-branch` to create one, "
        "then publish from there."
    )
